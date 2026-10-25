# Generated with an AI assistant
"""Evaluate exactly three repeat-aware variants under the frozen hold-out protocol."""
import csv
import hashlib
import json
import platform
import resource
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import scipy
from scipy import sparse
from threadpoolctl import threadpool_limits

from collaborative_models import personalized_pagerank
from compare_methods import average_precision_at_5, bootstrap_difference, load_counts, rank_scores
from repeat_aware_models import VARIANTS, fit_log_count_als

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / 'data' / 'processed', ROOT / 'reports'
REFERENCE = 'smoothed_personal_frequency'
OLD = ['personalized_pagerank', 'implicit_als']
METHODS = [REFERENCE]+OLD+list(VARIANTS)


def main():
    began = time.perf_counter()
    train = load_counts(DATA / 'train_interactions.csv')
    users = json.loads((DATA / 'all_users.json').read_text())
    uindex = {u: j for j, u in enumerate(users)}
    items = sorted({i for h in train.values() for i in h})
    iindex = {i: j for j, i in enumerate(items)}
    rr, cc, vv = [], [], []
    for u, h in train.items():
        for i, n in h.items():
            rr.append(uindex[u]); cc.append(iindex[i]); vv.append(n)
    counts = sparse.csr_matrix((np.array(vv, dtype=float), (rr, cc)), shape=(len(users), len(items)))
    candidates = np.array(json.loads((DATA / 'validation_candidates.json').read_text()), dtype=np.int64)
    candidate_set = set(candidates.tolist())
    mapping = np.array([iindex.get(int(i), -1) for i in candidates])
    supported = np.flatnonzero(mapping >= 0)
    popularity = Counter(i for h in train.values() for i in h)
    candidate_popularity = np.array([popularity[int(i)] for i in candidates], dtype=float)
    fallback = candidates[np.lexsort((candidates, -candidate_popularity))].tolist()
    # Same graph, item ordering and pruning as the original PPR experiment.
    original_dir = DATA / 'collaborative_models'
    with np.load(original_dir / 'als_factors.npz', allow_pickle=False) as original:
        assert original['item_ids'].tolist() == items and original['user_ids'].tolist() == users
    transition = sparse.load_npz(original_dir / 'ppr_transition.npz')
    dangling = np.asarray(transition.sum(axis=1)).ravel() == 0
    model_dir = DATA / 'repeat_aware_models'
    model_dir.mkdir(exist_ok=True)
    predictions, fills, top_scores = {}, {}, {}
    timings = {'shared_input_seconds': time.perf_counter()-began}
    convergence, objectives = [], {}
    start = time.perf_counter()
    recs, fill_counts, score_records = [], [], []
    for begin in range(0, len(users), 128):
        mass, diagnostic = personalized_pagerank(counts[begin:begin+128], transition, dangling)
        convergence.append(dict(batch_start=begin, **diagnostic))
        scores = np.zeros((mass.shape[0], len(candidates)))
        scores[:, supported] = mass[:, mapping[supported]]
        for row in scores:
            recommended, fill = rank_scores(row, candidates, candidate_popularity, fallback)
            recs.append(recommended); fill_counts.append(fill)
            score_records.append({i: float(row[np.searchsorted(candidates, i)]) for i in recommended})
    predictions['ppr_raw_counts'], fills['ppr_raw_counts'], top_scores['ppr_raw_counts'] = recs, fill_counts, score_records
    timings['ppr_raw_counts_predict_seconds'] = time.perf_counter()-start
    for method, alpha in [('als_log_counts_weighted', 20.), ('als_log_counts_uniform', 0.)]:
        start = time.perf_counter()
        uf, itf, objective = fit_log_count_als(counts, alpha=alpha)
        timings[method+'_fit_seconds'] = time.perf_counter()-start
        objectives[method] = objective
        np.savez_compressed(model_dir / (method+'.npz'), user_factors=uf, item_factors=itf,
                            user_ids=np.array(users), item_ids=np.array(items, dtype=np.int64))
        start = time.perf_counter()
        recs, fill_counts, score_records = [], [], []
        for begin in range(0, len(users), 128):
            scores = np.zeros((min(128, len(users)-begin), len(candidates)))
            scores[:, supported] = uf[begin:begin+128] @ itf[mapping[supported]].T
            for row in scores:
                recommended, fill = rank_scores(row, candidates, candidate_popularity, fallback)
                recs.append(recommended); fill_counts.append(fill)
                score_records.append({i: float(row[np.searchsorted(candidates, i)]) for i in recommended})
        predictions[method], fills[method], top_scores[method] = recs, fill_counts, score_records
        timings[method+'_predict_seconds'] = time.perf_counter()-start
    # New scores are fixed before reading any saved held-out AP or target behaviour.
    reference_records = {m: {} for m in [REFERENCE]+OLD}
    with (OUT / 'collaborative_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            reference_records[r['method']][r['user_id']] = r
    for method in [REFERENCE]+OLD:
        predictions[method], fills[method], top_scores[method] = [], [], []
        for u in users:
            r = reference_records[method][u]
            ids = list(map(int, r['tv_show_id'].split()))
            predictions[method].append(ids)
            fills[method].append(int(r['fallback_slots']))
            top_scores[method].append(dict(zip(ids, map(float, r['method_scores'].split()))))
    validation = load_counts(DATA / 'validation_interactions.csv')
    targets = {u: sorted(h, key=lambda i: (-h[i], i))[:5] for u, h in validation.items()}
    evaluated = [u for u in users if u in targets]
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    # Favourite definitions depend only on training and candidate availability.
    favorites, strong = {}, set()
    for u, h in train.items():
        item = min(h, key=lambda i: (-h[i], i))
        if item in candidate_set:
            favorites[u] = item
            if h[item] >= 10 and h[item]/sum(h.values()) >= .5:
                strong.add(u)
    cohorts = {'all_target_users': evaluated,
        'five_target_users': [u for u in evaluated if len(targets[u]) == 5],
        'template_target_users': [u for u in evaluated if u in template],
        'warm_target_users': [u for u in evaluated if u in train],
        'cold_target_users': [u for u in evaluated if u not in train],
        'light_history_target_users': [u for u in evaluated if 0 < sum(train.get(u, {}).values()) <= 10],
        'heavy_history_target_users': [u for u in evaluated if sum(train.get(u, {}).values()) >= 100],
        'strong_training_favorite_target_users': [u for u in evaluated if u in strong]}
    ap = {m: {u: average_precision_at_5(predictions[m][uindex[u]], set(targets[u])) for u in evaluated} for m in METHODS}
    for m in [REFERENCE]+OLD:
        assert all(abs(ap[m][u]-float(reference_records[m][u]['ap_at_5'])) < 1e-12 for u in evaluated)
    metrics = []
    for segment, members in cohorts.items():
        for method in METHODS:
            hits = [len(set(predictions[method][uindex[u]]) & set(targets[u])) for u in members]
            metrics.append({'segment': segment, 'method': method, 'users': len(members),
                'map_at_5': float(np.mean([ap[method][u] for u in members])),
                'precision_at_5': float(np.mean(hits)/5),
                'recall_at_5': float(np.mean([h/len(targets[u]) for h, u in zip(hits, members)])),
                'hit_rate_at_5': float(np.mean(np.array(hits) > 0))})
    with (OUT / 'repeat_aware_metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0])); writer.writeheader(); writer.writerows(metrics)
    with (OUT / 'repeat_aware_predictions.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'method', 'tv_show_id', 'method_scores', 'fallback_slots', 'ap_at_5', 'delta_vs_smoothed'])
        for u in users:
            j = uindex[u]
            for m in METHODS:
                ids = predictions[m][j]
                assert len(ids) == len(set(ids)) == 5 and set(ids) <= candidate_set and 0 not in ids
                if u not in train:
                    assert ids == fallback[:5]
                writer.writerow([u, m, ' '.join(map(str, ids)),
                    ' '.join(format(top_scores[m][j][i], '.17g') for i in ids), fills[m][j], ap[m].get(u, ''),
                    ap[m][u]-ap[REFERENCE][u] if u in targets else ''])
    comparisons = {}
    for m in VARIANTS:
        comparisons[m] = {}
        for reference in [REFERENCE, 'personalized_pagerank' if m == 'ppr_raw_counts' else 'implicit_als']:
            delta = [ap[m][u]-ap[reference][u] for u in evaluated]
            comparisons[m][reference] = dict(bootstrap_difference([ap[m][u] for u in evaluated], [ap[reference][u] for u in evaluated]),
                outcomes=dict(Counter('improved' if d > 1e-12 else 'worsened' if d < -1e-12 else 'unchanged' for d in delta)))
    diagnostics = {}
    strong_eval = cohorts['strong_training_favorite_target_users']
    relevant_strong = [u for u in strong_eval if favorites[u] in targets[u]]
    for m in METHODS:
        recs = {u: predictions[m][uindex[u]] for u in evaluated}
        diagnostics[m] = {'strong_favorite_users': len(strong_eval),
            'strong_favorite_retained': sum(favorites[u] in recs[u] for u in strong_eval),
            'strong_favorite_mean_capped_rank': float(np.mean([recs[u].index(favorites[u])+1 if favorites[u] in recs[u] else 6 for u in strong_eval])),
            'strong_favorite_also_validation_target_users': len(relevant_strong),
            'relevant_strong_favorite_retained': sum(favorites[u] in recs[u] for u in relevant_strong),
            'repeated_targets_training_count_ge_10': sum(train.get(u, {}).get(i, 0) >= 10 for u in evaluated for i in targets[u]),
            'repeated_target_hits_training_count_ge_10': sum(i in recs[u] and train.get(u, {}).get(i, 0) >= 10 for u in evaluated for i in targets[u]),
            'top5_hits_absent_from_own_training': sum(i in targets[u] and i not in train.get(u, {}) for u in evaluated for i in recs[u]),
            'fraction_recommendations_in_own_training': float(np.mean([i in train.get(u, {}) for u in evaluated for i in recs[u]])),
            'catalogue_items_recommended': len({i for r in recs.values() for i in r}),
            'target_items_added_vs_smoothed': sum(len((set(recs[u])-set(predictions[REFERENCE][uindex[u]])) & set(targets[u])) for u in evaluated),
            'target_items_removed_vs_smoothed': sum(len((set(predictions[REFERENCE][uindex[u]])-set(recs[u])) & set(targets[u])) for u in evaluated)}
    display = json.loads((DATA / 'display_metadata.json').read_text())
    fixed = json.loads((OUT / 'validation_examples.json').read_text())
    examples = []
    for e in fixed:
        u = e['user_id']
        record = {'label': e['label'], 'user_id': u, 'training_qualified_airings': sum(train[u].values()),
            'training_favorite': favorites.get(u), 'target_ids': targets[u], 'methods': {}}
        for m in METHODS:
            record['methods'][m] = {'ap_at_5': ap[m][u], 'recommendations': [
                {'rank': rank, 'tv_show_id': i, **display[str(i)], 'training_count': train[u].get(i, 0),
                 'validation_count': validation[u].get(i, 0), 'target_hit': i in targets[u],
                 'score': top_scores[m][uindex[u]][i]} for rank, i in enumerate(predictions[m][uindex[u]], 1)]}
        examples.append(record)
    (OUT / 'repeat_aware_examples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2)+'\n')
    summary = {'variants': VARIANTS,
        'selection': 'Exactly three manually fixed repeat-aware variants. No parameter sweep, validation early stopping or new fusion.',
        'known_holdout_warning': 'Variants motivated by previous errors on this same hold-out; results are model-selection evidence, not an untouched estimate.',
        'protocol': 'Unchanged temporal split, labels, MAP@5 population, candidate pool, repeats, positive-score ranking and popularity fallback.',
        'strong_favorite_definition': 'Training favorite has at least 10 qualified airings, at least 50% of personal training airings, and is in the common candidate pool. Ties use ascending ID.',
        'metrics': metrics, 'comparisons': comparisons, 'repeat_diagnostics': diagnostics,
        'ppr_convergence': convergence, 'als_training_objectives': objectives,
        'timings': timings, 'runtime_seconds': time.perf_counter()-began,
        'winner_on_primary_map': max(METHODS, key=lambda m: np.mean(list(ap[m].values()))),
        'peak_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_rss_units': 'bytes on macOS; KiB on Linux',
        'input_sha256': {n: hashlib.sha256((DATA / n).read_bytes()).hexdigest() for n in ['train_interactions.csv', 'validation_interactions.csv', 'validation_candidates.json']},
        'reference_sha256': {n: hashlib.sha256((OUT / n).read_bytes()).hexdigest() for n in ['collaborative_predictions.csv', 'collaborative_metrics.csv', 'smoothed_predictions.csv', 'validation_targets.csv']},
        'transition_sha256': hashlib.sha256((original_dir / 'ppr_transition.npz').read_bytes()).hexdigest(),
        'environment': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'blas_threads': 1}}
    (OUT / 'repeat_aware_results.json').write_text(json.dumps(summary, indent=2)+'\n')
    for r in metrics:
        if r['segment'] == 'all_target_users':
            print(f"{r['method']}: MAP@5={r['map_at_5']:.6f}")
    print(json.dumps({'winner': summary['winner_on_primary_map'], 'timings': timings, 'runtime_seconds': summary['runtime_seconds']}, indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()
