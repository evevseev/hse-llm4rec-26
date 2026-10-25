"""Independent checks: saved-factor ranks, dense implicit loss, PPR linear solve.

No model/evaluation project modules are imported. Uses NumPy/SciPy only for
linear algebra; metrics are independently calculated from saved targets.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / 'data' / 'processed', ROOT / 'reports'
MODEL = DATA / 'collaborative_models'


def main():
    summary = json.loads((OUT / 'collaborative_results.json').read_text())
    train = defaultdict(dict)
    with (DATA / 'train_interactions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            train[r['user_id']][int(r['tv_show_id'])] = int(r['qualified_airings'])
    users = json.loads((DATA / 'all_users.json').read_text())
    candidates = json.loads((DATA / 'validation_candidates.json').read_text())
    candidate_set = set(candidates)
    popularity = Counter(i for h in train.values() for i in h)
    fallback = sorted(candidates, key=lambda i: (-popularity[i], i))
    targets = {}
    with (OUT / 'validation_targets.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            targets[r['user_id']] = set(map(int, r['target_ids'].split()))
    predictions, ap, scores = defaultdict(dict), defaultdict(dict), defaultdict(dict)
    fills = defaultdict(dict)
    for name, expected in summary['input_sha256'].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == expected
    for name, expected in summary['reference_sha256'].items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == expected
    extension_hashes = json.loads((OUT / 'frequency_extension_verification.json').read_text())['new_artifact_sha256']
    assert hashlib.sha256((OUT / 'smoothed_predictions.csv').read_bytes()).hexdigest() == extension_hashes['smoothed_predictions.csv']
    with (OUT / 'collaborative_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            u, m = r['user_id'], r['method']
            assert u not in predictions[m]
            ids = list(map(int, r['tv_show_id'].split()))
            assert len(ids) == len(set(ids)) == 5 and set(ids) <= candidate_set and 0 not in ids
            predictions[m][u] = ids
            scores[m][u] = dict(zip(ids, map(float, r['method_scores'].split())))
            fills[m][u] = int(r['fallback_slots'])
            if u not in train:
                assert ids == fallback[:5] and int(r['fallback_slots']) == 5
            if u in targets:
                ranks = [rank for rank, i in enumerate(ids, 1) if i in targets[u]]
                value = sum(n/rank for n, rank in enumerate(ranks, 1))/len(targets[u])
                assert math.isclose(value, float(r['ap_at_5']), abs_tol=1e-12)
                ap[m][u] = value
    for m in predictions:
        assert set(predictions[m]) == set(users)
    with (OUT / 'smoothed_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            assert predictions['smoothed_personal_frequency'][r['user_id']] == list(map(int, r['tv_show_id'].split()))
    factors = np.load(MODEL / 'als_factors.npz', allow_pickle=False)
    uf, itf = factors['user_factors'], factors['item_factors']
    assert factors['user_ids'].tolist() == users
    items = factors['item_ids'].tolist()
    assert items == sorted({i for h in train.values() for i in h})
    item_index, user_index = {i: j for j, i in enumerate(items)}, {u: j for j, u in enumerate(users)}
    rr, cc, vv = [], [], []
    for u, h in train.items():
        for i, n in h.items():
            rr.append(user_index[u]); cc.append(item_index[i]); vv.append(n)
    counts = sparse.csr_matrix((np.array(vv, dtype=float), (rr, cc)), shape=(len(users), len(items)))
    reg, alpha = .1, 20.
    # Independently evaluate every implicit loss term using explicit dense blocks.
    dense_loss = 0.
    for begin in range(0, len(users), 128):
        dense_counts = counts[begin:begin+128].toarray()
        confidence = 1+alpha*np.log1p(dense_counts)
        preference = (dense_counts > 0).astype(float)
        predicted = uf[begin:begin+128] @ itf.T
        dense_loss += np.sum(confidence*(preference-predicted)**2)
    dense_loss += reg*(np.sum(uf**2)+np.sum(itf**2))
    recorded_loss = summary['als_training_objective'][-1]['training_objective']
    assert math.isclose(dense_loss, recorded_loss, rel_tol=1e-10)
    losses = [r['training_objective'] for r in summary['als_training_objective']]
    assert all(b <= a+1e-7*max(1, a) for a, b in zip(losses, losses[1:]))
    # The item block is the last ALS update: check its normal equations independently.
    rng = np.random.default_rng(42)
    sample_items = sorted(set(rng.choice(len(items), size=100, replace=False).tolist()+np.argsort(np.asarray((counts > 0).sum(axis=0)).ravel())[-5:].tolist()))
    csc, max_relative = counts.tocsc(), 0.
    for item in sample_items:
        left, right = csc.indptr[item:item+2]
        us, ns = csc.indices[left:right], csc.data[left:right]
        conf = 1+20*np.log1p(ns)
        system = uf.T @ uf + uf[us].T @ ((conf-1)[:, None]*uf[us]) + .1*np.eye(32)
        target = uf[us].T @ conf
        relative = np.linalg.norm(system @ itf[item]-target)/(1+np.linalg.norm(target))
        max_relative = max(max_relative, float(relative))
    assert max_relative < 1e-9

    def ranked(score_by_item):
        selected = sorted((i for i in candidates if score_by_item.get(i, 0) > 0),
                          key=lambda i: (-score_by_item[i], -popularity[i], i))[:5]
        fill = 5-len(selected)
        selected += [i for i in fallback if i not in selected][:fill]
        return selected, fill

    supported = [i for i in candidates if i in item_index]
    supported_cols = [item_index[i] for i in supported]
    for begin in range(0, len(users), 128):
        values = uf[begin:begin+128] @ itf[supported_cols].T
        for offset, row in enumerate(values):
            u = users[begin+offset]
            score_by_item = dict(zip(supported, row.tolist()))
            expected, fill = ranked(score_by_item)
            assert expected == predictions['implicit_als'][u] and fill == fills['implicit_als'][u]
            for i in expected:
                assert math.isclose(score_by_item.get(i, 0), scores['implicit_als'][u][i], abs_tol=1e-12)
    # Rebuild graph sample rows from training viewers, independent of graph construction code.
    graph, transition = sparse.load_npz(MODEL / 'ppr_graph.npz'), sparse.load_npz(MODEL / 'ppr_transition.npz')
    assert graph.shape == transition.shape == (len(items), len(items))
    assert np.all(graph.diagonal() == 0) and np.diff(graph.indptr).max() <= 50
    assert np.all(graph.data > 0) and graph.data.max() <= 1+1e-12
    degree = np.asarray(graph.sum(axis=1)).ravel()
    expected_transition = sparse.diags(np.divide(1, degree, out=np.zeros_like(degree), where=degree > 0)) @ graph
    difference = (expected_transition-transition).tocsr()
    assert difference.nnz == 0 or np.max(np.abs(difference.data)) < 1e-12
    binary = counts.copy(); binary.data[:] = 1
    pair_counts = (binary.T @ binary).tocsr()
    viewers = np.asarray(binary.sum(axis=0)).ravel()
    graph_sample = sorted(set(rng.choice(len(items), 60, replace=False).tolist()+[item_index[2400480], item_index[12001682]]))
    for i in graph_sample:
        supports = pair_counts.getrow(i).toarray().ravel()
        js = [j for j in range(len(items)) if j != i and supports[j] >= 3]
        similarity = {j: supports[j]/math.sqrt(viewers[i]*viewers[j]) for j in js}
        wanted = sorted(js, key=lambda j: (-similarity[j], j))[:50]
        assert set(graph.getrow(i).indices) == set(wanted)
        for j in wanted:
            assert math.isclose(float(graph[i, j]), similarity[j], abs_tol=1e-12)
    # A linear-system solution is independent of the model's power iteration.
    warm = [u for u in users if u in train]
    sampled_users = sorted(set(rng.choice(warm, 30, replace=False).tolist()+['10500740270951698446', '12453026253397466416']), key=int)
    seed_rows = []
    for u in sampled_users:
        seed = np.zeros(len(items))
        for i, n in train[u].items():
            seed[item_index[i]] = math.log1p(n)
        seed_rows.append(seed/seed.sum())
    seeds = np.array(seed_rows)
    solved = splu((sparse.eye(len(items))-.85*transition.T).tocsc()).solve(seeds.T).T
    solved /= solved.sum(axis=1, keepdims=True)
    exact_rank_matches = 0
    max_score_difference = 0.
    for k, u in enumerate(sampled_users):
        by_item = {i: float(solved[k, item_index[i]]) for i in supported}
        expected, _ = ranked(by_item)
        actual = predictions['personalized_pagerank'][u]
        exact_rank_matches += actual == expected
        for rank, i in enumerate(actual):
            difference = abs(by_item.get(i, 0)-scores['personalized_pagerank'][u][i])
            max_score_difference = max(max_score_difference, difference)
            assert difference < 2e-8
            # Permit only negligible numerical differences at ranking ties.
            assert abs(by_item.get(i, 0)-by_item.get(expected[rank], 0)) < 2e-8
    assert all(r['converged'] for r in summary['ppr_convergence'])
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    cohorts = {'all_target_users': set(targets),
        'five_target_users': {u for u in targets if len(targets[u]) == 5},
        'template_target_users': set(targets) & template,
        'warm_target_users': set(targets) & set(train), 'cold_target_users': set(targets)-set(train),
        'light_history_target_users': {u for u in targets if 0 < sum(train.get(u, {}).values()) <= 10},
        'heavy_history_target_users': {u for u in targets if sum(train.get(u, {}).values()) >= 100}}
    metric_rows = 0
    with (OUT / 'collaborative_metrics.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            members, m = cohorts[r['segment']], r['method']
            hits = {u: len(set(predictions[m][u]) & targets[u]) for u in members}
            assert int(r['users']) == len(members)
            expected_metrics = {'map_at_5': sum(ap[m][u] for u in members)/len(members),
                'precision_at_5': sum(hits.values())/(5*len(members)),
                'recall_at_5': sum(hits[u]/len(targets[u]) for u in members)/len(members),
                'hit_rate_at_5': sum(h > 0 for h in hits.values())/len(members)}
            assert all(math.isclose(value, float(r[key]), abs_tol=1e-12) for key, value in expected_metrics.items())
            metric_rows += 1
    report = {'status': 'passed', 'prediction_rows_checked': sum(map(len, predictions.values())),
        'metric_rows_independently_recomputed': metric_rows,
        'original_reference_hash_unchanged': True,
        'als_rankings_rebuilt_from_saved_factors': len(users), 'als_dense_objective': dense_loss,
        'als_item_normal_equations_checked': len(sample_items), 'als_max_relative_normal_equation_residual': max_relative,
        'ppr_graph_rows_independently_rebuilt': len(graph_sample), 'ppr_users_checked_by_linear_solve': len(sampled_users),
        'ppr_exact_top5_rank_matches': exact_rank_matches, 'ppr_max_saved_score_vs_linear_solution_difference': max_score_difference,
        'artifact_sha256': {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in ['collaborative_predictions.csv', 'collaborative_metrics.csv', 'collaborative_results.json']}}
    (OUT / 'collaborative_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()
