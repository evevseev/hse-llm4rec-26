# Generated with an AI assistant
"""Independent verification of frozen references, three variants and repeat diagnostics.

No training/evaluation project modules are imported. Factor predictions and
objectives are reconstructed directly; PPR is checked by a sparse linear solve.
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


def main():
    result = json.loads((OUT / 'repeat_aware_results.json').read_text())
    original = json.loads((OUT / 'collaborative_results.json').read_text())
    assert result['input_sha256'] == original['input_sha256']
    for name, digest in result['input_sha256'].items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == digest
    for name, digest in result['reference_sha256'].items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == digest
    old_hashes = json.loads((OUT / 'collaborative_verification.json').read_text())['artifact_sha256']
    assert result['reference_sha256']['collaborative_predictions.csv'] == old_hashes['collaborative_predictions.csv']
    assert result['reference_sha256']['collaborative_metrics.csv'] == old_hashes['collaborative_metrics.csv']
    assert result['reference_sha256']['validation_targets.csv'] == original['reference_sha256']['validation_targets.csv']
    assert result['reference_sha256']['smoothed_predictions.csv'] == original['reference_sha256']['smoothed_predictions.csv']
    train = defaultdict(dict)
    with (DATA / 'train_interactions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            train[r['user_id']][int(r['tv_show_id'])] = int(r['qualified_airings'])
    users = json.loads((DATA / 'all_users.json').read_text())
    items = sorted({i for h in train.values() for i in h})
    ui, ii = {u: j for j, u in enumerate(users)}, {i: j for j, i in enumerate(items)}
    candidates = json.loads((DATA / 'validation_candidates.json').read_text())
    popularity = Counter(i for h in train.values() for i in h)
    fallback = sorted(candidates, key=lambda i: (-popularity[i], i))
    rr, cc, vv = [], [], []
    for u, h in train.items():
        for i, n in h.items():
            rr.append(ui[u]); cc.append(ii[i]); vv.append(n)
    counts = sparse.csr_matrix((np.array(vv, dtype=float), (rr, cc)), shape=(len(users), len(items)))
    targets = {}
    with (OUT / 'validation_targets.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            targets[r['user_id']] = set(map(int, r['target_ids'].split()))
    predictions, scores, ap, fills = defaultdict(dict), defaultdict(dict), defaultdict(dict), defaultdict(dict)
    with (OUT / 'repeat_aware_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            u, m = r['user_id'], r['method']
            assert u not in predictions[m]
            ids = list(map(int, r['tv_show_id'].split()))
            assert len(ids) == len(set(ids)) == 5 and set(ids) <= set(candidates) and 0 not in ids
            predictions[m][u] = ids
            scores[m][u] = dict(zip(ids, map(float, r['method_scores'].split())))
            fills[m][u] = int(r['fallback_slots'])
            if u not in train:
                assert ids == fallback[:5] and fills[m][u] == 5
            if u in targets:
                ranks = [rank for rank, i in enumerate(ids, 1) if i in targets[u]]
                value = sum(n/rank for n, rank in enumerate(ranks, 1))/len(targets[u])
                assert math.isclose(value, float(r['ap_at_5']), abs_tol=1e-12)
                ap[m][u] = value
            else:
                assert r['ap_at_5'] == r['delta_vs_smoothed'] == ''
    for m in predictions:
        assert set(predictions[m]) == set(users)
    with (OUT / 'collaborative_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            assert predictions[r['method']][r['user_id']] == list(map(int, r['tv_show_id'].split()))
    supported = [i for i in candidates if i in ii]
    columns = [ii[i] for i in supported]

    def ranked(by_item):
        selected = sorted((i for i in candidates if by_item.get(i, 0) > 0),
                          key=lambda i: (-by_item[i], -popularity[i], i))[:5]
        fill = 5-len(selected)
        selected += [i for i in fallback if i not in selected][:fill]
        return selected, fill

    rng = np.random.default_rng(42)
    checked_models = {}
    for method, alpha in [('als_log_counts_weighted', 20.), ('als_log_counts_uniform', 0.)]:
        artifact = np.load(DATA / 'repeat_aware_models' / (method+'.npz'), allow_pickle=False)
        assert artifact['user_ids'].tolist() == users and artifact['item_ids'].tolist() == items
        uf, itf = artifact['user_factors'], artifact['item_factors']
        loss = 0.
        for begin in range(0, len(users), 128):
            dense_counts = counts[begin:begin+128].toarray()
            target = np.log1p(dense_counts)
            confidence = 1+alpha*target
            prediction = uf[begin:begin+128] @ itf.T
            loss += np.sum(confidence*(target-prediction)**2)
            candidate_scores = uf[begin:begin+128] @ itf[columns].T
            for k, row in enumerate(candidate_scores):
                u = users[begin+k]
                by_item = dict(zip(supported, row.tolist()))
                expected, fill = ranked(by_item)
                assert expected == predictions[method][u] and fill == fills[method][u]
                for i in expected:
                    assert math.isclose(by_item.get(i, 0), scores[method][u][i], abs_tol=1e-12)
        loss += .1*(np.sum(uf**2)+np.sum(itf**2))
        history = result['als_training_objectives'][method]
        assert math.isclose(loss, history[-1]['training_objective'], rel_tol=1e-10)
        assert all(b['training_objective'] <= a['training_objective']+1e-7*max(1, a['training_objective']) for a, b in zip(history, history[1:]))
        # Item updates are last; final user updates precede them and are not stationary assertions.
        csc = counts.tocsc()
        sampled = sorted(set(rng.choice(len(items), 100, replace=False).tolist()+[ii[2400480], ii[12001682]]))
        max_residual = 0.
        for j in sampled:
            left, right = csc.indptr[j:j+2]
            us = csc.indices[left:right]
            target = np.log1p(csc.data[left:right])
            c = 1+alpha*target
            system = uf.T @ uf+uf[us].T @ ((c-1)[:, None]*uf[us])+.1*np.eye(32)
            response = uf[us].T @ (c*target)
            residual = float(np.linalg.norm(system @ itf[j]-response)/(1+np.linalg.norm(response)))
            max_residual = max(max_residual, residual)
        assert max_residual < 1e-9
        checked_models[method] = {'all_rankings_rebuilt': len(users), 'dense_training_loss': loss,
                                 'normal_equations_checked': len(sampled), 'maximum_relative_residual': max_residual}
    transition_path = DATA / 'collaborative_models' / 'ppr_transition.npz'
    assert hashlib.sha256(transition_path.read_bytes()).hexdigest() == result['transition_sha256']
    transition = sparse.load_npz(transition_path)
    sampled_users = sorted(set(rng.choice(list(train), 30, replace=False).tolist()+['10500740270951698446', '12453026253397466416']), key=int)
    seeds = np.zeros((len(sampled_users), len(items)))
    for row, u in enumerate(sampled_users):
        for i, n in train[u].items():
            seeds[row, ii[i]] = n
        seeds[row] /= seeds[row].sum()
    direct = splu((sparse.eye(len(items))-.85*transition.T).tocsc()).solve(seeds.T).T
    direct /= direct.sum(axis=1, keepdims=True)
    exact_matches, max_difference = 0, 0.
    for row, u in enumerate(sampled_users):
        by_item = {i: float(direct[row, ii[i]]) for i in supported}
        expected, _ = ranked(by_item)
        actual = predictions['ppr_raw_counts'][u]
        exact_matches += expected == actual
        for rank, i in enumerate(actual):
            difference = abs(by_item.get(i, 0)-scores['ppr_raw_counts'][u][i])
            max_difference = max(max_difference, difference)
            assert difference < 2e-8
            assert abs(by_item.get(i, 0)-by_item.get(expected[rank], 0)) < 2e-8
    assert all(d['converged'] for d in result['ppr_convergence'])
    favorite, strong = {}, set()
    for u, h in train.items():
        i = min(h, key=lambda item: (-h[item], item))
        if i in candidates:
            favorite[u] = i
            if h[i] >= 10 and h[i]/sum(h.values()) >= .5:
                strong.add(u)
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    cohorts = {'all_target_users': set(targets),
        'five_target_users': {u for u in targets if len(targets[u]) == 5},
        'template_target_users': set(targets) & template, 'warm_target_users': set(targets) & set(train),
        'cold_target_users': set(targets)-set(train),
        'light_history_target_users': {u for u in targets if 0 < sum(train.get(u, {}).values()) <= 10},
        'heavy_history_target_users': {u for u in targets if sum(train.get(u, {}).values()) >= 100},
        'strong_training_favorite_target_users': set(targets) & strong}
    metric_rows = 0
    with (OUT / 'repeat_aware_metrics.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            m, members = r['method'], cohorts[r['segment']]
            assert int(r['users']) == len(members)
            hits = {u: len(set(predictions[m][u]) & targets[u]) for u in members}
            values = {'map_at_5': sum(ap[m][u] for u in members)/len(members),
                'precision_at_5': sum(hits.values())/(5*len(members)),
                'recall_at_5': sum(hits[u]/len(targets[u]) for u in members)/len(members),
                'hit_rate_at_5': sum(v > 0 for v in hits.values())/len(members)}
            assert all(math.isclose(v, float(r[k]), abs_tol=1e-12) for k, v in values.items())
            metric_rows += 1
    for m, saved in result['repeat_diagnostics'].items():
        strong_eval = cohorts['strong_training_favorite_target_users']
        relevant_strong = {u for u in strong_eval if favorite[u] in targets[u]}
        assert saved['strong_favorite_users'] == len(strong_eval)
        assert saved['strong_favorite_retained'] == sum(favorite[u] in predictions[m][u] for u in strong_eval)
        assert saved['strong_favorite_also_validation_target_users'] == len(relevant_strong)
        assert saved['relevant_strong_favorite_retained'] == sum(favorite[u] in predictions[m][u] for u in relevant_strong)
        assert saved['repeated_targets_training_count_ge_10'] == sum(train.get(u, {}).get(i, 0) >= 10 for u in targets for i in targets[u])
        assert saved['repeated_target_hits_training_count_ge_10'] == sum(i in predictions[m][u] and train.get(u, {}).get(i, 0) >= 10 for u in targets for i in targets[u])
    report = {'status': 'passed', 'original_inputs_and_reference_hashes_unchanged': True,
        'prediction_rows_checked': sum(map(len, predictions.values())),
        'cohort_metric_rows_independently_recomputed': metric_rows, 'repeated_target_and_strong_favorite_diagnostics_recomputed': True,
        'matrix_factorizations': checked_models,
        'ppr_direct_linear_solve_users': len(sampled_users), 'ppr_exact_top5_matches': exact_matches,
        'ppr_max_score_difference_from_linear_solution': max_difference,
        'artifact_sha256': {n: hashlib.sha256((OUT / n).read_bytes()).hexdigest() for n in ['repeat_aware_predictions.csv', 'repeat_aware_metrics.csv', 'repeat_aware_results.json']}}
    (OUT / 'repeat_aware_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()
