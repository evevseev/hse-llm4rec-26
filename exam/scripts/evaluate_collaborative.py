"""Compare fixed PPR and implicit ALS against the saved smoothed-frequency model.

Run: .venv/bin/python scripts/evaluate_collaborative.py
All model predictions are finalized before loading held-out viewing counts.
"""
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
from threadpoolctl import threadpool_info, threadpool_limits

from collaborative_models import (ALS_PARAMETERS, PPR_PARAMETERS, build_transition,
                                  fit_implicit_als, personalized_pagerank)
from compare_methods import average_precision_at_5, bootstrap_difference, load_counts, rank_scores

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'processed'
OUT = ROOT / 'reports'
REFERENCE = 'smoothed_personal_frequency'
METHODS = [REFERENCE, 'personalized_pagerank', 'implicit_als']


def main():
    began = time.perf_counter()
    train = load_counts(DATA / 'train_interactions.csv')
    users = json.loads((DATA / 'all_users.json').read_text())
    uindex = {u: j for j, u in enumerate(users)}
    # Fit only the observed training item catalogue, not a future-feature catalogue.
    items = sorted({i for h in train.values() for i in h})
    iindex = {i: j for j, i in enumerate(items)}
    rr, cc, vv = [], [], []
    for user, history in train.items():
        for item, count in history.items():
            rr.append(uindex[user]); cc.append(iindex[item]); vv.append(count)
    counts = sparse.csr_matrix((np.array(vv, dtype=float), (rr, cc)), shape=(len(users), len(items)))
    candidates = np.array(json.loads((DATA / 'validation_candidates.json').read_text()), dtype=np.int64)
    mapping = np.array([iindex.get(int(i), -1) for i in candidates])
    eligible = np.flatnonzero(mapping >= 0)
    pop = Counter(i for history in train.values() for i in history)
    candidate_pop = np.array([pop[int(i)] for i in candidates], dtype=float)
    fallback = candidates[np.lexsort((candidates, -candidate_pop))].tolist()
    predictions, fills, top_scores = {}, {}, {}
    timings = {'shared_input_seconds': time.perf_counter()-began}
    model_dir = DATA / 'collaborative_models'
    model_dir.mkdir(exist_ok=True)
    seeds = counts.copy()
    seeds.data = np.log1p(seeds.data)
    normalized = sparse.diags(1/np.maximum(np.asarray(seeds.sum(axis=1)).ravel(), 1e-30)) @ seeds
    start = time.perf_counter()
    transition, dangling, graph = build_transition(counts, neighbors=50, min_pair_users=3)
    timings['ppr_graph_fit_seconds'] = time.perf_counter()-start
    sparse.save_npz(model_dir / 'ppr_transition.npz', transition)
    sparse.save_npz(model_dir / 'ppr_graph.npz', graph)
    ppr_recs, ppr_fill, ppr_scores, convergence = [], [], [], []
    start = time.perf_counter()
    for begin in range(0, len(users), 128):
        ranks, diagnostic = personalized_pagerank(normalized[begin:begin+128].tocsr(), transition, dangling)
        convergence.append(dict(batch_start=begin, **diagnostic))
        scores = np.zeros((ranks.shape[0], len(candidates)))
        scores[:, eligible] = ranks[:, mapping[eligible]]
        for row in scores:
            recs, fill = rank_scores(row, candidates, candidate_pop, fallback)
            ppr_recs.append(recs); ppr_fill.append(fill)
            ppr_scores.append({i: float(row[np.searchsorted(candidates, i)]) for i in recs})
    timings['ppr_predict_seconds'] = time.perf_counter()-start
    predictions['personalized_pagerank'], fills['personalized_pagerank'] = ppr_recs, ppr_fill
    top_scores['personalized_pagerank'] = ppr_scores
    start = time.perf_counter()
    uf, itf, objective = fit_implicit_als(counts)
    timings['als_fit_seconds'] = time.perf_counter()-start
    np.savez_compressed(model_dir / 'als_factors.npz', user_factors=uf, item_factors=itf,
                        user_ids=np.array(users), item_ids=np.array(items, dtype=np.int64))
    als_recs, als_fill, als_scores = [], [], []
    start = time.perf_counter()
    for begin in range(0, len(users), 128):
        scores = np.zeros((min(128, len(users)-begin), len(candidates)))
        scores[:, eligible] = uf[begin:begin+128] @ itf[mapping[eligible]].T
        for row in scores:
            recs, fill = rank_scores(row, candidates, candidate_pop, fallback)
            als_recs.append(recs); als_fill.append(fill)
            als_scores.append({i: float(row[np.searchsorted(candidates, i)]) for i in recs})
    timings['als_predict_seconds'] = time.perf_counter()-start
    predictions['implicit_als'], fills['implicit_als'] = als_recs, als_fill
    top_scores['implicit_als'] = als_scores
    # Load the saved reference, without refitting, after constructing new predictions.
    reference, reference_ap, reference_fill = {}, {}, {}
    with (OUT / 'smoothed_predictions.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            u = row['user_id']
            reference[u] = list(map(int, row['tv_show_id'].split()))
            reference_fill[u] = int(row['fallback_slots'])
            if row['ap_at_5']:
                reference_ap[u] = float(row['ap_at_5'])
    predictions[REFERENCE] = [reference[u] for u in users]
    fills[REFERENCE] = [reference_fill[u] for u in users]
    top_scores[REFERENCE] = [{i: train.get(u, {}).get(i, 0)+3*pop[i]/max(candidate_pop) for i in reference[u]} for u in users]
    # Held-out behaviour is used from this point onward for evaluation only.
    validation = load_counts(DATA / 'validation_interactions.csv')
    targets = {u: sorted(h, key=lambda i: (-h[i], i))[:5] for u, h in validation.items()}
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    evaluated = [u for u in users if u in targets]
    cohorts = {
        'all_target_users': evaluated,
        'five_target_users': [u for u in evaluated if len(targets[u]) == 5],
        'template_target_users': [u for u in evaluated if u in template],
        'warm_target_users': [u for u in evaluated if u in train],
        'cold_target_users': [u for u in evaluated if u not in train],
        'light_history_target_users': [u for u in evaluated if 0 < sum(train.get(u, {}).values()) <= 10],
        'heavy_history_target_users': [u for u in evaluated if sum(train.get(u, {}).values()) >= 100]}
    ap = {method: {u: average_precision_at_5(predictions[method][uindex[u]], set(targets[u])) for u in evaluated} for method in METHODS}
    assert all(abs(ap[REFERENCE][u]-reference_ap[u]) < 1e-12 for u in evaluated)
    rows = []
    for cohort, members in cohorts.items():
        for method in METHODS:
            hits = [len(set(predictions[method][uindex[u]]) & set(targets[u])) for u in members]
            rows.append({'segment': cohort, 'method': method, 'users': len(members),
                'map_at_5': float(np.mean([ap[method][u] for u in members])),
                'precision_at_5': float(np.mean(hits)/5),
                'recall_at_5': float(np.mean([h/len(targets[u]) for h, u in zip(hits, members)])),
                'hit_rate_at_5': float(np.mean(np.array(hits) > 0))})
    with (OUT / 'collaborative_metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (OUT / 'collaborative_predictions.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'method', 'tv_show_id', 'method_scores', 'fallback_slots', 'ap_at_5', 'delta_vs_smoothed'])
        for u in users:
            j = uindex[u]
            for method in METHODS:
                recs = predictions[method][j]
                assert len(set(recs)) == len(recs) == 5 and set(recs) <= set(candidates.tolist()) and 0 not in recs
                if u not in train:
                    assert recs == fallback[:5]
                writer.writerow([u, method, ' '.join(map(str, recs)),
                    ' '.join(format(top_scores[method][j][i], '.17g') for i in recs), fills[method][j],
                    ap[method].get(u, ''), ap[method][u]-ap[REFERENCE][u] if u in targets else ''])
    comparisons, diagnostics = {}, {}
    for method in METHODS[1:]:
        differences = {u: ap[method][u]-ap[REFERENCE][u] for u in evaluated}
        comparisons[method] = dict(bootstrap_difference([ap[method][u] for u in evaluated], [ap[REFERENCE][u] for u in evaluated]),
            user_outcomes=dict(Counter('improved' if d > 1e-12 else 'worsened' if d < -1e-12 else 'unchanged' for d in differences.values())))
    for method in METHODS:
        recs = {u: predictions[method][uindex[u]] for u in evaluated}
        new_target_hits = sum(i in targets[u] and i not in train.get(u, {}) for u, rec in recs.items() for i in rec)
        diagnostics[method] = {
            'catalogue_items_recommended': len({i for rec in recs.values() for i in rec}),
            'fraction_recommendations_in_own_training': float(np.mean([i in train.get(u, {}) for u, rec in recs.items() for i in rec])),
            'mean_fallback_slots': float(np.mean([fills[method][uindex[u]] for u in evaluated])),
            'top5_hits_absent_from_own_training': new_target_hits,
            'target_hits_added_vs_smoothed': sum(len((set(recs[u])-set(reference[u])) & set(targets[u])) for u in evaluated),
            'target_hits_removed_vs_smoothed': sum(len((set(reference[u])-set(recs[u])) & set(targets[u])) for u in evaluated)}
    display = json.loads((DATA / 'display_metadata.json').read_text())
    original_examples = json.loads((OUT / 'validation_examples.json').read_text())
    chosen = [(e['label'], e['user_id'], 'Previously fixed heavy/light viewer.') for e in original_examples]
    for method in METHODS[1:]:
        for label, sign in [('largest_gain', 1), ('largest_loss', -1)]:
            user = max(evaluated, key=lambda u: (sign*(ap[method][u]-ap[REFERENCE][u]), -int(u)))
            chosen.append((method+'_'+label, user, 'Outcome-selected diagnostic, not a representative sample.'))
    examples = []
    for label, u, selection in chosen:
        example = {'label': label, 'user_id': u, 'selection': selection,
            'training_qualified_airings': sum(train.get(u, {}).values()),
            'targets': [{'tv_show_id': i, **display[str(i)], 'validation_count': validation[u][i]} for i in targets[u]], 'methods': {}}
        for method in METHODS:
            example['methods'][method] = {'ap_at_5': ap[method][u], 'recommendations': [
                {'rank': rank, 'tv_show_id': i, **display[str(i)], 'score': top_scores[method][uindex[u]][i],
                 'training_count': train.get(u, {}).get(i, 0), 'validation_count': validation[u].get(i, 0),
                 'target_hit': i in targets[u]} for rank, i in enumerate(predictions[method][uindex[u]], 1)]}
        examples.append(example)
    (OUT / 'collaborative_examples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2)+'\n')
    summary = {'parameters': {'ppr': PPR_PARAMETERS, 'implicit_als': ALS_PARAMETERS,
                    'selection': 'One fixed configuration per model; no validation search or hybrid.',
                    'rank_rule': 'Positive model scores, then popularity and item ID; fill from original popularity. Cold users use the identical fallback.'},
        'protocol': 'Unchanged weeks 11–20 training / 21–30 validation; >=80% merged coverage; same candidates, labels and repeats.',
        'metrics': rows, 'comparisons_vs_smoothed': comparisons, 'recommendation_diagnostics': diagnostics,
        'model_sizes': {'training_users': len(train), 'training_items': len(items), 'training_user_item_pairs': counts.nnz,
            'graph_directed_edges': graph.nnz, 'graph_dangling_nodes': int(dangling.sum()), 'candidates_without_training_history': int((mapping < 0).sum())},
        'ppr_convergence': convergence, 'als_training_objective': objective, 'timings': timings,
        'winner_on_primary_map': max(METHODS, key=lambda m: np.mean(list(ap[m].values()))),
        'runtime_seconds': time.perf_counter()-began, 'peak_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_rss_units': 'bytes on macOS; KiB on Linux',
        'input_sha256': {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest() for name in ['train_interactions.csv', 'validation_interactions.csv', 'validation_candidates.json']},
        'reference_sha256': {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in ['smoothed_predictions.csv', 'validation_targets.csv']},
        'environment': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__,
                        'scipy': scipy.__version__, 'threadpools': threadpool_info(), 'blas_threads': 1}}
    (OUT / 'collaborative_results.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: summary[k] for k in ['model_sizes', 'comparisons_vs_smoothed', 'timings', 'winner_on_primary_map', 'runtime_seconds']}, indent=2))
    for row in rows:
        if row['segment'] == 'all_target_users':
            print(f"{row['method']}: MAP@5={row['map_at_5']:.6f}")


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()
