"""Audit temporal supervision, cached features, model replay and held-out metrics.

Labels and numeric count checks are rebuilt without importing training/evaluation
scripts. Snapshot regeneration is a reproducibility check of the feature module;
critical count/popularity/schedule features are also checked directly.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from ltr_features import (BEGIN, FEATURES, OUTER_CUTOFF, OUTER_END, WINDOWS, Snapshot,
                          load_events, load_schedule)
from xgboost_runtime import XGBRanker

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / 'data' / 'processed' / 'learning_to_rank', ROOT / 'reports'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(path):
    result = defaultdict(dict)
    with path.open(newline='') as f:
        for r in csv.DictReader(f):
            result[r['user_id']][int(r['tv_show_id'])] = int(r['qualified_airings'])
    return dict(result)


def ap5(predicted, relevant):
    ranks = [rank for rank, i in enumerate(predicted, 1) if i in relevant]
    return sum(n/rank for n, rank in enumerate(ranks, 1))/len(relevant)


def main():
    training = json.loads((OUT / 'ltr_training_results.json').read_text())
    result = json.loads((OUT / 'ltr_results.json').read_text())
    barrier = json.loads((OUT / 'ltr_prediction_manifest.json').read_text())
    assert sha(DATA / 'ranker.ubj') == training['model_sha256'] == barrier['model_sha256'] == result['model_sha256']
    assert sha(DATA / 'training_examples.npz') == training['training_examples_sha256']
    assert sha(OUT / 'ltr_predictions.csv') == barrier['prediction_sha256']
    assert sha(DATA / 'evaluation_features.npz') == barrier['evaluation_features_sha256']
    assert sha(OUT / 'ltr_plan.json') == training['plan_sha256']
    original = json.loads((OUT / 'collaborative_results.json').read_text())
    assert sha(ROOT / 'data' / 'processed' / 'train_interactions.csv') == original['input_sha256']['train_interactions.csv'] == training['training_counts_sha256']
    assert sha(ROOT / 'data' / 'processed' / 'validation_interactions.csv') == original['input_sha256']['validation_interactions.csv'] == result['held_out_counts_sha256']
    assert sha(OUT / 'validation_targets.csv') == original['reference_sha256']['validation_targets.csv'] == result['original_targets_sha256']
    assert sha(OUT / 'smoothed_predictions.csv') == original['reference_sha256']['smoothed_predictions.csv'] == result['reference_predictions_sha256']
    events = load_events()
    train = counts(ROOT / 'data' / 'processed' / 'train_interactions.csv')
    assert Counter((u, i) for u, i, _, _, _, _ in events) == Counter({(u, i): n for u, h in train.items() for i, n in h.items()})
    with (DATA / 'history' / 'training_airing_details.csv').open(newline='') as f:
        detail = list(csv.DictReader(f))
    assert all(0 < int(r['overlap_seconds']) <= int(r['airing_duration_seconds']) and
               5*int(r['overlap_seconds']) >= 4*int(r['airing_duration_seconds']) for r in detail)
    schedule = load_schedule(['export_arh_11-20-final.csv'])
    airing_keys = set(schedule)
    assert all((i, c, a, b) in airing_keys and BEGIN <= a < b <= OUTER_CUTOFF for _, i, c, a, b, _ in events)
    assert len({(u, i, c, a, b) for u, i, c, a, b, _ in events}) == len(events)
    del detail, airing_keys
    matrix = np.load(DATA / 'training_examples.npz', allow_pickle=False)
    X, y, group = matrix['X'], matrix['y'], matrix['group']
    with (OUT / 'ltr_training_queries.csv').open(newline='') as f:
        queries = list(csv.DictReader(f))
    assert len(group) == len(queries) == training['training_queries']
    assert len(X) == len(y) == int(group.sum()) == training['training_rows']
    assert int(y.sum()) == training['positive_rows'] and X.shape[1] == len(FEATURES)
    users_train = sorted({e[0] for e in events}, key=int)
    regenerated_rows = regenerated_labels = 0
    windows_audit = []
    for name, cutoff, finish in WINDOWS:
        assert finish <= OUTER_CUTOFF
        # Independent target construction from time-filtered qualified airings.
        target_counts = defaultdict(Counter)
        for u, item, _, start, end, _ in events:
            if cutoff <= start < end <= finish:
                target_counts[u][item] += 1
        targets = {u: set(sorted(h, key=lambda i: (-h[i], i))[:5]) for u, h in target_counts.items()}
        snapshot = Snapshot(events, schedule, users_train, cutoff, finish)
        assert snapshot.history_max_end <= cutoff
        window_queries = [r for r in queries if r['window'] == name]
        for query in window_queries:
            u = query['user_id']
            start, n = int(query['row_start']), int(query['rows'])
            assert int(query['history_cutoff_epoch']) == cutoff and int(query['label_end_epoch']) == finish
            # Positive injection order in training follows frequency, not sorted ID.
            target_order = sorted(target_counts[u], key=lambda i: (-target_counts[u][i], i))[:5]
            positions, features, added = snapshot.candidates_and_features(u, target_order)
            ids = snapshot.items[positions]
            labels = np.array([int(int(i) in targets[u]) for i in ids], dtype=np.uint8)
            np.testing.assert_array_equal(features, X[start:start+n])
            np.testing.assert_array_equal(labels, y[start:start+n])
            assert len(ids) == n and added == int(query['injected_positives'])
            regenerated_rows += n; regenerated_labels += int(labels.sum())
        windows_audit.append({'window': name, 'queries_checked': len(window_queries),
                              'maximum_history_end': snapshot.history_max_end, 'label_end': finish})
        del snapshot
    assert regenerated_rows == len(X) and regenerated_labels == int(y.sum())
    del X, y, group, matrix
    # All outer feature rows and natural candidates are regenerated without labels.
    outer = np.load(DATA / 'evaluation_features.npz', allow_pickle=False)
    X, item_ids, group, margins = outer['X'], outer['item_ids'], outer['group'], outer['margins']
    users = outer['users'].tolist()
    schedule = load_schedule(['export_arh_11-20-final.csv', 'export_arh_21-30-final.csv'])
    snapshot = Snapshot(events, schedule, users, OUTER_CUTOFF, OUTER_END)
    assert snapshot.history_max_end <= OUTER_CUTOFF
    assert snapshot.items.tolist() == json.loads((ROOT / 'data' / 'processed' / 'validation_candidates.json').read_text())
    predictions = {}
    with (OUT / 'ltr_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            assert r['user_id'] not in predictions
            predictions[r['user_id']] = r
    assert set(predictions) == set(users) and np.all(group == 100)
    offset, candidate_sets = 0, {}
    for row, u in enumerate(users):
        n = int(group[row])
        positions, features, injected = snapshot.candidates_and_features(u)
        assert injected == 0
        np.testing.assert_array_equal(snapshot.items[positions], item_ids[offset:offset+n])
        np.testing.assert_array_equal(features, X[offset:offset+n])
        candidate_sets[u] = set(map(int, item_ids[offset:offset+n]))
        offset += n
    # Direct count/popularity checks for a deterministic user sample.
    rng = np.random.default_rng(42)
    sampled = set(rng.choice(users, 30, replace=False).tolist()+['10500740270951698446', '12453026253397466416'])
    direct_pop = Counter(i for h in train.values() for i in h)
    for u in sampled:
        row = snapshot.user_index[u]
        left = int(sum(group[:row])); right = left+int(group[row])
        for j, i in enumerate(item_ids[left:right]):
            i = int(i)
            assert X[left+j, FEATURES.index('personal_count')] == train.get(u, {}).get(i, 0)
            assert X[left+j, FEATURES.index('global_viewers')] == direct_pop[i]
    model = XGBRanker(); model.load_model(DATA / 'ranker.ubj')
    assert model.get_booster().num_boosted_rounds() == 120 and model.n_features_in_ == len(FEATURES)
    saved_config = json.loads(model.get_booster().save_config())
    assert saved_config['learner']['objective']['name'] == 'rank:pairwise'
    replay = model.predict(X).astype(float)
    cold = snapshot.user_total == 0
    replay[np.repeat(cold, group)] = 0
    np.testing.assert_array_equal(replay, margins)
    ranker = {}
    offset = 0
    for row, u in enumerate(users):
        n = int(group[row]); ids, values = item_ids[offset:offset+n], margins[offset:offset+n]
        if cold[row]:
            expected = snapshot.items[snapshot.fallback].tolist()
        else:
            popularity = np.array([direct_pop[int(i)] for i in ids])
            expected = ids[np.lexsort((ids, -popularity, -values))[:5]].tolist()
        actual = list(map(int, predictions[u]['tv_show_id'].split()))
        assert actual == expected and len(actual) == len(set(actual)) == 5
        assert int(predictions[u]['fallback_slots']) == (5 if cold[row] else 0)
        ranker[u] = actual
        offset += n
    validation = counts(ROOT / 'data' / 'processed' / 'validation_interactions.csv')
    targets = {u: set(sorted(h, key=lambda i: (-h[i], i))[:5]) for u, h in validation.items()}
    reference = {}
    with (OUT / 'smoothed_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            reference[r['user_id']] = list(map(int, r['tv_show_id'].split()))
    assert all(set(reference[u]) <= candidate_sets[u] for u in users)
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    methods = {'history_schedule_ranker': ranker, 'smoothed_personal_frequency': reference,
               'popularity': {u: snapshot.items[snapshot.fallback].tolist() for u in users}}
    aps = {m: {u: ap5(ps[u], targets[u]) for u in targets} for m, ps in methods.items()}
    cohorts = {'all_target_users': set(targets), 'five_target_users': {u for u in targets if len(targets[u]) == 5},
        'template_target_users': set(targets) & template, 'warm_target_users': set(targets) & set(train),
        'cold_target_users': set(targets)-set(train),
        'light_history_target_users': {u for u in targets if 0 < sum(train.get(u, {}).values()) <= 10},
        'heavy_history_target_users': {u for u in targets if sum(train.get(u, {}).values()) >= 100}}
    metric_rows = 0
    with (OUT / 'ltr_metrics.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            m, members = r['method'], cohorts[r['segment']]
            hits = {u: len(set(methods[m][u]) & targets[u]) for u in members}
            expected = {'map_at_5': sum(aps[m][u] for u in members)/len(members),
                'precision_at_5': sum(hits.values())/(5*len(members)),
                'recall_at_5': sum(hits[u]/len(targets[u]) for u in members)/len(members),
                'hit_rate_at_5': sum(h > 0 for h in hits.values())/len(members)}
            assert int(r['users']) == len(members)
            assert all(math.isclose(value, float(r[key]), abs_tol=1e-12) for key, value in expected.items())
            metric_rows += 1
    candidate_recall = sum(len(candidate_sets[u] & targets[u])/len(targets[u]) for u in targets)/len(targets)
    assert math.isclose(candidate_recall, result['candidate_mean_target_recall'], abs_tol=1e-12)
    oracle = sum(aps['smoothed_personal_frequency'][u] if u not in train else
                 len(candidate_sets[u] & targets[u])/len(targets[u]) for u in targets)/len(targets)
    assert math.isclose(oracle, result['oracle_map_at_5_with_fixed_cold_fallback'], abs_tol=1e-12)
    for method, ps in methods.items():
        hits_new = sum(i in targets[u] and i not in train.get(u, {}) for u in targets for i in ps[u])
        hits_global_new = sum(i in targets[u] and direct_pop[i] == 0 for u in targets for i in ps[u])
        assert result['diagnostics'][method]['target_hits_absent_from_own_training'] == hits_new
        assert result['diagnostics'][method]['target_hits_without_any_training_viewer'] == hits_global_new
    outcomes = Counter('improved' if aps['history_schedule_ranker'][u]-aps['smoothed_personal_frequency'][u] > 1e-12 else
                       'worsened' if aps['history_schedule_ranker'][u]-aps['smoothed_personal_frequency'][u] < -1e-12 else 'unchanged' for u in targets)
    assert outcomes == result['user_outcomes']
    report = {'status': 'passed', 'qualified_history_airings_reconciled': len(events),
        'all_supervised_labels_end_before_outer_validation': True, 'training_windows': windows_audit,
        'training_feature_rows_regenerated': regenerated_rows, 'training_positive_labels_rebuilt': regenerated_labels,
        'outer_feature_rows_regenerated_without_labels': len(X), 'outer_candidates_per_user': 100,
        'outer_positive_injection': 0, 'model_margin_rows_replayed': len(replay),
        'all_ranker_top5_lists_rebuilt': len(users), 'reference_top5_in_candidates_for_every_user': True,
        'direct_count_feature_sample_users': len(sampled), 'cohort_metric_rows_recomputed': metric_rows,
        'frozen_original_inputs_and_reference_hashes_match': True,
        'artifact_retry_preserved_model_and_predictions': barrier.get('same_predictions_as_previous_attempt'),
        'artifact_sha256': {n: sha(OUT / n) for n in ['ltr_predictions.csv', 'ltr_metrics.csv', 'ltr_results.json', 'ltr_training_results.json']}}
    (OUT / 'ltr_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()
