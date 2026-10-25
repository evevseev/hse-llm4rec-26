"""Freeze ranker predictions, then evaluate once on the existing weeks 21–30 labels."""
import csv
import hashlib
import json
import resource
import time
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.special import expit
from threadpoolctl import threadpool_limits

from compare_methods import average_precision_at_5, bootstrap_difference, load_counts
from ltr_features import FEATURES, OUTER_CUTOFF, OUTER_END, Snapshot, load_events, load_schedule
from xgboost_runtime import XGBRanker

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / 'data' / 'processed' / 'learning_to_rank', ROOT / 'reports'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    began = time.perf_counter()
    training = json.loads((OUT / 'ltr_training_results.json').read_text())
    assert training['model_sha256'] == digest(DATA / 'ranker.ubj')
    previous_barrier = json.loads((OUT / 'ltr_prediction_manifest.json').read_text()) if (OUT / 'ltr_prediction_manifest.json').exists() else None
    if previous_barrier:
        assert previous_barrier['model_sha256'] == training['model_sha256'], 'Do not silently evaluate a different model on this hold-out.'
    model = XGBRanker(); model.load_model(DATA / 'ranker.ubj')
    events = load_events()
    users = json.loads((ROOT / 'data' / 'processed' / 'all_users.json').read_text())
    schedule = load_schedule(['export_arh_11-20-final.csv', 'export_arh_21-30-final.csv'])
    snapshot = Snapshot(events, schedule, users, OUTER_CUTOFF, OUTER_END)
    expected = json.loads((ROOT / 'data' / 'processed' / 'validation_candidates.json').read_text())
    assert snapshot.items.tolist() == expected
    feature_blocks, item_blocks, groups = [], [], []
    for u in users:
        positions, features, injected = snapshot.candidates_and_features(u)
        assert injected == 0 and len(positions) == 100
        feature_blocks.append(features); item_blocks.append(snapshot.items[positions]); groups.append(len(positions))
    X, item_ids = np.concatenate(feature_blocks), np.concatenate(item_blocks)
    del feature_blocks, item_blocks
    margins = model.predict(X).astype(float)
    group = np.array(groups, dtype=np.uint32)
    cold = snapshot.user_total == 0
    margins[np.repeat(cold, group)] = 0
    np.savez_compressed(DATA / 'evaluation_features.npz', X=X, item_ids=item_ids, group=group, margins=margins, users=np.array(users))
    predictions, candidate_sets, score_by_user = {}, {}, {}
    offset = 0
    for row, u in enumerate(users):
        n = int(group[row]); ids, values = item_ids[offset:offset+n], margins[offset:offset+n]
        candidate_sets[u] = set(map(int, ids))
        if cold[row]:
            recommendations = snapshot.items[snapshot.fallback].tolist()
            score_by_user[u] = {i: 0. for i in recommendations}
        else:
            popularity = np.array([snapshot.popularity[snapshot.item_index[int(i)]] for i in ids])
            order = np.lexsort((ids, -popularity, -values))[:5]
            recommendations = ids[order].tolist()
            score_by_user[u] = dict(zip(map(int, ids), map(float, values)))
        predictions[u] = recommendations
        offset += n
    with (OUT / 'ltr_predictions.csv').open('w', newline='') as f:
        writer = csv.writer(f); writer.writerow(['user_id', 'tv_show_id', 'ranking_margins', 'monotone_scores', 'fallback_slots'])
        for row, u in enumerate(users):
            raw = [score_by_user[u][i] for i in predictions[u]]
            writer.writerow([u, ' '.join(map(str, predictions[u])), ' '.join(format(v, '.17g') for v in raw),
                ' '.join(format(float(expit(v)), '.17g') for v in raw), 5 if cold[row] else 0])
    # Freeze hashes before opening held-out behaviour: this is the evaluation barrier.
    barrier = {'predictions_frozen_at_epoch': time.time(), 'model_sha256': digest(DATA / 'ranker.ubj'),
        'prediction_sha256': digest(OUT / 'ltr_predictions.csv'),
        'evaluation_features_sha256': digest(DATA / 'evaluation_features.npz'),
        'history_cutoff_epoch': OUTER_CUTOFF, 'maximum_history_event_end': snapshot.history_max_end,
        'held_out_viewing_counts_loaded': False, 'injected_outer_positives': 0, 'candidates_per_user': 100,
        'evaluation_script_attempts': previous_barrier.get('evaluation_script_attempts', 1)+1 if previous_barrier else 1,
        'same_predictions_as_previous_attempt': previous_barrier['prediction_sha256'] == digest(OUT / 'ltr_predictions.csv') if previous_barrier else None}
    if previous_barrier:
        assert barrier['same_predictions_as_previous_attempt'], 'An artifact retry must preserve the frozen predictions.'
    (OUT / 'ltr_prediction_manifest.json').write_text(json.dumps(barrier, indent=2)+'\n')
    prediction_seconds = time.perf_counter()-began
    # Validation behaviour is first accessed below, only for quality calculation.
    validation = load_counts(ROOT / 'data' / 'processed' / 'validation_interactions.csv')
    train = load_counts(ROOT / 'data' / 'processed' / 'train_interactions.csv')
    targets = {u: sorted(h, key=lambda i: (-h[i], i))[:5] for u, h in validation.items()}
    reference, reference_ap = {}, {}
    with (OUT / 'smoothed_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            reference[r['user_id']] = list(map(int, r['tv_show_id'].split()))
            if r['ap_at_5']:
                reference_ap[r['user_id']] = float(r['ap_at_5'])
    assert all(set(reference[u]) <= candidate_sets[u] for u in users)
    evaluated = [u for u in users if u in targets]
    pop = snapshot.items[snapshot.fallback].tolist()
    methods = {'history_schedule_ranker': predictions, 'smoothed_personal_frequency': reference,
               'popularity': {u: pop for u in users}}
    ap = {m: {u: average_precision_at_5(ps[u], set(targets[u])) for u in evaluated} for m, ps in methods.items()}
    assert all(abs(ap['smoothed_personal_frequency'][u]-reference_ap[u]) < 1e-12 for u in evaluated)
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    cohorts = {'all_target_users': evaluated,
        'five_target_users': [u for u in evaluated if len(targets[u]) == 5],
        'template_target_users': [u for u in evaluated if u in template],
        'warm_target_users': [u for u in evaluated if u in train],
        'cold_target_users': [u for u in evaluated if u not in train],
        'light_history_target_users': [u for u in evaluated if 0 < sum(train.get(u, {}).values()) <= 10],
        'heavy_history_target_users': [u for u in evaluated if sum(train.get(u, {}).values()) >= 100]}
    metrics = []
    for segment, members in cohorts.items():
        for m, ps in methods.items():
            hits = [len(set(ps[u]) & set(targets[u])) for u in members]
            metrics.append({'segment': segment, 'method': m, 'users': len(members),
                'map_at_5': float(np.mean([ap[m][u] for u in members])),
                'precision_at_5': float(np.mean(hits)/5),
                'recall_at_5': float(np.mean([h/len(targets[u]) for h, u in zip(hits, members)])),
                'hit_rate_at_5': float(np.mean(np.array(hits) > 0))})
    with (OUT / 'ltr_metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0])); writer.writeheader(); writer.writerows(metrics)
    with (OUT / 'ltr_per_user_metrics.csv').open('w', newline='') as f:
        writer = csv.writer(f); writer.writerow(['user_id', 'ranker_ap_at_5', 'reference_ap_at_5', 'ap_delta', 'candidate_target_recall'])
        for u in evaluated:
            writer.writerow([u, ap['history_schedule_ranker'][u], reference_ap[u],
                ap['history_schedule_ranker'][u]-reference_ap[u], len(candidate_sets[u] & set(targets[u]))/len(targets[u])])
    deltas = [ap['history_schedule_ranker'][u]-reference_ap[u] for u in evaluated]
    comparisons = bootstrap_difference([ap['history_schedule_ranker'][u] for u in evaluated], [reference_ap[u] for u in evaluated])
    outcome = dict(Counter('improved' if d > 1e-12 else 'worsened' if d < -1e-12 else 'unchanged' for d in deltas))
    retrieval = [len(candidate_sets[u] & set(targets[u]))/len(targets[u]) for u in evaluated]
    oracle = [reference_ap[u] if u not in train else len(candidate_sets[u] & set(targets[u]))/len(targets[u]) for u in evaluated]
    diagnostics = {}
    for m, ps in methods.items():
        diagnostics[m] = {'catalogue_items_recommended': len({i for u in evaluated for i in ps[u]}),
            'target_hits_absent_from_own_training': sum(i in targets[u] and i not in train.get(u, {}) for u in evaluated for i in ps[u]),
            'target_hits_without_any_training_viewer': int(sum(i in targets[u] and snapshot.popularity[snapshot.item_index[i]] == 0 for u in evaluated for i in ps[u]))}
    display = json.loads((ROOT / 'data' / 'processed' / 'display_metadata.json').read_text())
    fixed = json.loads((OUT / 'validation_examples.json').read_text())
    examples = []
    for e in fixed:
        u = e['user_id']
        examples.append({'label': e['label'], 'user_id': u, 'target_ids': targets[u],
            'target_ids_in_candidates': sorted(candidate_sets[u] & set(targets[u])),
            'methods': {m: {'ap_at_5': ap[m][u], 'recommendations': [
                {'rank': rank, 'tv_show_id': i, **display[str(i)], 'training_count': train[u].get(i, 0),
                 'validation_count': validation[u].get(i, 0), 'target_hit': i in targets[u]}
                 for rank, i in enumerate(ps[u], 1)]} for m, ps in methods.items()}})
    (OUT / 'ltr_examples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2)+'\n')
    result = {'metrics': metrics, 'comparison_vs_reference': comparisons, 'user_outcomes': outcome,
        'candidate_mean_target_recall': float(np.mean(retrieval)),
        'oracle_map_at_5_with_fixed_cold_fallback': float(np.mean(oracle)),
        'reference_top5_in_candidates_for_all_users': True, 'diagnostics': diagnostics,
        'prediction_and_feature_seconds': prediction_seconds, 'runtime_seconds': time.perf_counter()-began,
        'unique_outer_model_configurations_evaluated': 1, 'outer_model_tuning': False,
        'evaluation_script_attempts': barrier['evaluation_script_attempts'],
        'artifact_retry_note': 'Initial evaluation reached JSON export but failed on a NumPy integer; the corrected export preserves the identical model and prediction hashes.' if previous_barrier else None,
        'model_sha256': barrier['model_sha256'], 'prediction_manifest_sha256': digest(OUT / 'ltr_prediction_manifest.json'),
        'original_targets_sha256': digest(OUT / 'validation_targets.csv'),
        'reference_predictions_sha256': digest(OUT / 'smoothed_predictions.csv'),
        'held_out_counts_sha256': digest(ROOT / 'data' / 'processed' / 'validation_interactions.csv'),
        'peak_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_rss_units': 'bytes on macOS; KiB on Linux'}
    (OUT / 'ltr_results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['comparison_vs_reference', 'user_outcomes', 'candidate_mean_target_recall', 'oracle_map_at_5_with_fixed_cold_fallback', 'runtime_seconds']}, indent=2))
    for r in metrics:
        if r['segment'] == 'all_target_users':
            print(f"{r['method']}: MAP@5={r['map_at_5']:.6f}")


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()
