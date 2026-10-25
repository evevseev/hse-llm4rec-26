"""Run a frozen 20-configuration grid in parallel; confirm only frozen finalists.

Usage: .venv/bin/python scripts/run_hyperparameter_search.py --stage primary
       .venv/bin/python scripts/run_hyperparameter_search.py --stage secondary
Workers load training inputs only. The coordinator scores predictions after all
runs finish. Configurations have separate processes/artifacts and no warm starts.
"""
import argparse
import csv
import hashlib
import json
import multiprocessing
import os
import platform
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits

from collaborative_models import build_transition, personalized_pagerank
from compare_methods import average_precision_at_5, bootstrap_difference, item_features, load_counts, rank_scores
from repeat_aware_models import fit_log_count_als
from search_plan import plan

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports' / 'hyperparameter_search'
CONTEXT = None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initialize_worker(fold_dir):
    global CONTEXT
    directory = Path(fold_dir)
    train = load_counts(directory / 'train_interactions.csv')
    users = json.loads((directory / 'all_users.json').read_text())
    metadata = json.loads((directory / 'training_metadata.json').read_text())
    candidates = np.array(json.loads((directory / 'validation_candidates.json').read_text()), dtype=np.int64)
    observed = sorted({i for h in train.values() for i in h})
    all_items = sorted(set(observed) | set(candidates.tolist()) | {int(i) for i in metadata})
    all_index = {i: j for j, i in enumerate(all_items)}
    user_index = {u: j for j, u in enumerate(users)}
    rr, cc, vv = [], [], []
    for u, h in train.items():
        for i, n in h.items():
            rr.append(user_index[u]); cc.append(all_index[i]); vv.append(n)
    all_counts = sparse.csr_matrix((np.array(vv, dtype=float), (rr, cc)), shape=(len(users), len(all_items)))
    observed_columns = np.array([all_index[i] for i in observed])
    candidate_columns = np.array([all_index[int(i)] for i in candidates])
    observed_index = {i: j for j, i in enumerate(observed)}
    observed_mapping = np.array([observed_index.get(int(i), -1) for i in candidates])
    supported = np.flatnonzero(observed_mapping >= 0)
    counts = all_counts[:, observed_columns].tocsr()
    binary = all_counts.copy(); binary.data[:] = 1
    popularity = np.asarray(binary.sum(axis=0)).ravel()
    candidate_popularity = popularity[candidate_columns]
    fallback = candidates[np.lexsort((candidates, -candidate_popularity))].tolist()
    cold = np.diff(all_counts.indptr) == 0
    CONTEXT = dict(directory=directory, train=train, users=users, metadata=metadata,
        candidates=candidates, all_items=all_items, all_index=all_index, all_counts=all_counts,
        counts=counts, observed=observed, observed_mapping=observed_mapping, supported=supported,
        candidate_columns=candidate_columns, binary=binary, popularity=popularity,
        candidate_popularity=candidate_popularity, fallback=fallback, cold=cold)


def fit_and_score(config):
    c = CONTEXT
    family = config['family']
    diagnostics, model = {}, {}
    counts, all_counts = c['counts'], c['all_counts']
    if family == 'frequency':
        model['bonus'] = config['bonus']*c['candidate_popularity']/max(c['candidate_popularity'])
    elif family == 'ppr':
        transition, dangling, graph = build_transition(counts)
        seeds = counts.copy()
        if config['history'] == 'log':
            seeds.data = np.log1p(seeds.data)
        model.update(transition=transition, dangling=dangling, seeds=seeds)
        diagnostics['graph_edges'] = graph.nnz
        diagnostics['convergence'] = []
    elif family == 'mf':
        uf, itf, objective = fit_log_count_als(counts, alpha=config['alpha'], factors=config['factors'],
            regularization=config['regularization'], iterations=15, seed=42)
        model.update(user_factors=uf, item_factors=itf)
        diagnostics['training_objective'] = objective
    elif family == 'cbf':
        feature_ids = sorted(int(i) for i in c['metadata'])
        vectorizer = DictVectorizer(dtype=np.float64)
        features = vectorizer.fit_transform([item_features(c['metadata'][str(i)]) for i in feature_ids])
        features = TfidfTransformer(norm='l2', smooth_idf=True).fit_transform(features)
        coordinate = features.tocoo()
        padded = sparse.csr_matrix((coordinate.data,
            ([c['all_index'][feature_ids[r]] for r in coordinate.row], coordinate.col)),
            shape=(len(c['all_items']), features.shape[1]))
        weights = all_counts.copy()
        if config['history'] == 'log':
            weights.data = np.log1p(weights.data)
        model.update(profiles=normalize(weights @ padded, norm='l2'),
                     candidate_features=padded[c['candidate_columns']])
        diagnostics['content_features'] = features.shape[1]
    elif family == 'association_rules':
        pairs = (c['binary'].T @ c['binary']).tocsr()
        rr, cc, vv = [], [], []
        for i in range(len(c['all_items'])):
            left, right = pairs.indptr[i:i+2]
            js, support = pairs.indices[left:right], pairs.data[left:right]
            confidence = support/max(c['popularity'][i], 1)
            keep = (js != i) & (support >= 3) & (confidence >= .02)
            js, support, confidence = js[keep], support[keep], confidence[keep]
            weights = confidence*support/(support+10)
            order = np.lexsort((np.array(c['all_items'])[js], -weights))[:100]
            rr.extend([i]*len(order)); cc.extend(js[order].tolist()); vv.extend(weights[order].tolist())
        rules = sparse.csr_matrix((vv, (rr, cc)), shape=(len(c['all_items']), len(c['all_items'])))
        history = all_counts.copy()
        if config['history'] == 'log':
            history.data = np.log1p(history.data)
        model.update(history=history, candidate_rules=rules[:, c['candidate_columns']])
        diagnostics['rules'] = rules.nnz
    else:
        raise ValueError(family)
    return model, diagnostics


def run_configuration(config, result_dir):
    c = CONTEXT
    started = time.time()
    began = time.perf_counter()
    directory = Path(result_dir) / config['id']
    directory.mkdir(exist_ok=True)
    with threadpool_limits(limits=1):
        model, diagnostics = fit_and_score(config)
        fit_seconds = time.perf_counter()-began
        if config['family'] == 'mf':
            np.savez_compressed(directory / 'factors.npz', user_factors=model['user_factors'],
                item_factors=model['item_factors'], user_ids=np.array(c['users']), item_ids=np.array(c['observed'], dtype=np.int64))
        predict_start = time.perf_counter()
        with (directory / 'predictions.csv').open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'tv_show_id', 'scores', 'fallback_slots'])
            for begin in range(0, len(c['users']), 128):
                finish = min(len(c['users']), begin+128)
                family = config['family']
                if family == 'frequency':
                    scores = c['all_counts'][begin:finish, c['candidate_columns']].toarray()+model['bonus']
                elif family == 'ppr':
                    ranks, diagnostic = personalized_pagerank(model['seeds'][begin:finish], model['transition'],
                        model['dangling'], damping=config['damping'])
                    diagnostics['convergence'].append(diagnostic)
                    scores = np.zeros((finish-begin, len(c['candidates'])))
                    scores[:, c['supported']] = ranks[:, c['observed_mapping'][c['supported']]]
                elif family == 'mf':
                    scores = np.zeros((finish-begin, len(c['candidates'])))
                    scores[:, c['supported']] = model['user_factors'][begin:finish] @ model['item_factors'][c['observed_mapping'][c['supported']]].T
                elif family == 'cbf':
                    scores = (model['profiles'][begin:finish] @ model['candidate_features'].T).toarray()
                else:
                    scores = (model['history'][begin:finish] @ model['candidate_rules']).toarray()
                scores[c['cold'][begin:finish]] = 0
                for offset, row in enumerate(scores):
                    ids, fill = rank_scores(row, c['candidates'], c['candidate_popularity'], c['fallback'])
                    writer.writerow([c['users'][begin+offset], ' '.join(map(str, ids)),
                        ' '.join(format(float(row[np.searchsorted(c['candidates'], i)]), '.17g') for i in ids), fill])
        predict_seconds = time.perf_counter()-predict_start
    record = {'config': config, 'pid': os.getpid(), 'start_epoch': started, 'end_epoch': time.time(),
        'fit_seconds': fit_seconds, 'predict_and_export_seconds': predict_seconds,
        'runtime_seconds': time.perf_counter()-began, 'diagnostics': diagnostics,
        'peak_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_rss_units': 'bytes on macOS; KiB on Linux', 'blas_threads': 1}
    (directory / 'run.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def score_stage(stage, configs, fold_dir, records, elapsed):
    directory = OUT / stage
    train = load_counts(fold_dir / 'train_interactions.csv')
    validation = load_counts(fold_dir / 'validation_interactions.csv')
    targets = {u: sorted(h, key=lambda i: (-h[i], i))[:5] for u, h in validation.items()}
    users = json.loads((fold_dir / 'all_users.json').read_text())
    candidates = set(json.loads((fold_dir / 'validation_candidates.json').read_text()))
    evaluated = [u for u in users if u in targets]
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    cohorts = {'all_target_users': evaluated,
        'five_target_users': [u for u in evaluated if len(targets[u]) == 5],
        'template_target_users': [u for u in evaluated if u in template],
        'warm_target_users': [u for u in evaluated if u in train],
        'cold_target_users': [u for u in evaluated if u not in train],
        'light_history_target_users': [u for u in evaluated if 0 < sum(train.get(u, {}).values()) <= 10],
        'heavy_history_target_users': [u for u in evaluated if sum(train.get(u, {}).values()) >= 100]}
    popularity = {i: sum(i in h for h in train.values()) for i in candidates}
    pop_top5 = sorted(candidates, key=lambda i: (-popularity[i], i))[:5]
    predictions, aps = {}, {}
    for config in configs:
        key = config['id']
        with (directory / key / 'predictions.csv').open(newline='') as f:
            records_by_user = {r['user_id']: r for r in csv.DictReader(f)}
        assert set(records_by_user) == set(users)
        ids_by_user = {u: list(map(int, r['tv_show_id'].split())) for u, r in records_by_user.items()}
        assert all(len(ids) == len(set(ids)) == 5 and set(ids) <= candidates for ids in ids_by_user.values())
        assert all(ids_by_user[u] == pop_top5 for u in users if u not in train)
        predictions[key] = ids_by_user
        aps[key] = {u: average_precision_at_5(ids_by_user[u], set(targets[u])) for u in evaluated}
        with (directory / key / 'scored_predictions.csv').open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'tv_show_id', 'scores', 'fallback_slots', 'ap_at_5'])
            for u in users:
                r = records_by_user[u]
                writer.writerow([u, r['tv_show_id'], r['scores'], r['fallback_slots'], aps[key].get(u, '')])
    predictions['popularity_reference'] = {u: pop_top5 for u in users}
    aps['popularity_reference'] = {u: average_precision_at_5(pop_top5, set(targets[u])) for u in evaluated}
    metrics = []
    for segment, members in cohorts.items():
        for key in predictions:
            hits = [len(set(predictions[key][u]) & set(targets[u])) for u in members]
            metrics.append({'segment': segment, 'config_id': key, 'users': len(members),
                'map_at_5': float(np.mean([aps[key][u] for u in members])),
                'precision_at_5': float(np.mean(hits)/5),
                'recall_at_5': float(np.mean([h/len(targets[u]) for h, u in zip(hits, members)])),
                'hit_rate_at_5': float(np.mean(np.array(hits) > 0))})
    with (directory / 'metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0])); writer.writeheader(); writer.writerows(metrics)
    primary = {r['config_id']: r['map_at_5'] for r in metrics if r['segment'] == 'all_target_users'}
    ranking = sorted((dict(c, map_at_5=primary[c['id']]) for c in configs), key=lambda r: (-r['map_at_5'], r['id']))
    (directory / 'ranking.json').write_text(json.dumps(ranking, indent=2)+'\n')
    comparison = {}
    for row in ranking:
        key = row['id']
        comparison[key] = bootstrap_difference([aps[key][u] for u in evaluated], [aps['frequency_bonus_3'][u] for u in evaluated])
    with (directory / 'targets.csv').open('w', newline='') as f:
        writer = csv.writer(f); writer.writerow(['user_id', 'tv_show_id'])
        writer.writerows((u, ' '.join(map(str, targets[u]))) for u in evaluated)
    # In-flight intervals establish that runs actually overlapped, not just used a pool API.
    endpoints = sorted([(r['start_epoch'], 1) for r in records]+[(r['end_epoch'], -1) for r in records], key=lambda x: (x[0], x[1]))
    active, maximum = 0, 0
    for _, change in endpoints:
        active += change; maximum = max(maximum, active)
    summary = {'stage': stage, 'ranking': ranking, 'comparisons_vs_reference': comparison,
        'metrics': metrics, 'population': {name: len(members) for name, members in cohorts.items()},
        'all_log_users': len(users), 'users_without_targets': len(users)-len(targets),
        'candidate_items': len(candidates), 'worker_pids': sorted({r['pid'] for r in records}),
        'maximum_observed_concurrent_runs': maximum, 'parallel_fit_wall_seconds': elapsed,
        'runs': records, 'input_sha256': {n: sha(fold_dir / n) for n in ['train_interactions.csv', 'validation_interactions.csv', 'validation_candidates.json', 'training_metadata.json', 'all_users.json']},
        'plan_sha256': sha(ROOT / 'reports' / 'hyperparameter_plan.json'),
        'environment': {'python': sys.version, 'platform': platform.platform()}}
    (directory / 'results.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(f'{stage}: {len(configs)} runs; max concurrent={maximum}; best={ranking[0]["id"]}, MAP@5={ranking[0]["map_at_5"]:.6f}', flush=True)
    return summary


def select_robust_configuration(primary, secondary, rule):
    candidates = []
    for config in secondary['ranking']:
        key = config['id']
        first = primary['comparisons_vs_reference'][key]['mean_delta']
        second = secondary['comparisons_vs_reference'][key]['mean_delta']
        lower = secondary['comparisons_vs_reference'][key]['paired_bootstrap_95_percent_interval'][0]
        if first > 0 and second > 0 and lower > 0:
            candidates.append({'config_id': key, 'minimum_fold_gain': min(first, second),
                'primary_map_at_5': next(r['map_at_5'] for r in primary['ranking'] if r['id'] == key)})
    candidates.sort(key=lambda r: (-r['minimum_fold_gain'], -r['primary_map_at_5'], r['config_id']))
    return {'rule': rule, 'eligible_candidates': candidates,
        'selected_config_id': candidates[0]['config_id'] if candidates else 'frequency_bonus_3',
        'reason': 'Passed the prespecified cross-fold checks.' if candidates else 'No finalist passed all prespecified robustness checks; retain the reference.'}


def main(stage):
    protocol = json.loads((ROOT / 'reports' / 'hyperparameter_plan.json').read_text())
    assert protocol == plan(), 'Saved plan differs from code; do not silently change the grid.'
    assert len(protocol['configurations']) == 20
    fold_dir = ROOT / protocol['folds'][stage]['data_dir']
    configs = protocol['configurations']
    if stage == 'secondary':
        frozen = json.loads((OUT / 'finalists.json').read_text())
        assert frozen['primary_ranking_sha256'] == sha(OUT / 'primary' / 'ranking.json')
        configs = [c for c in configs if c['id'] in frozen['confirmation_ids']]
    (OUT / stage).mkdir(parents=True, exist_ok=True)
    workers = min(4, os.cpu_count() or 1)
    began = time.perf_counter()
    records = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                             initializer=initialize_worker, initargs=(str(fold_dir),)) as executor:
        futures = {executor.submit(run_configuration, c, str(OUT / stage)): c['id'] for c in configs}
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            print(f'{stage}: finished {record["config"]["id"]} in {record["runtime_seconds"]:.2f}s (PID {record["pid"]})', flush=True)
    result = score_stage(stage, configs, fold_dir, records, time.perf_counter()-began)
    if stage == 'primary':
        top = [r['id'] for r in result['ranking'][:4]]
        confirmation = list(dict.fromkeys(top+['frequency_bonus_3']))
        frozen = {'top_four_primary_ids': top, 'confirmation_ids': confirmation,
            'primary_ranking_sha256': sha(OUT / 'primary' / 'ranking.json'),
            'plan_sha256': sha(ROOT / 'reports' / 'hyperparameter_plan.json'),
            'frozen_at_epoch': time.time(), 'selection_used_secondary_scores': False}
        (OUT / 'finalists.json').write_text(json.dumps(frozen, indent=2)+'\n')
    else:
        primary = json.loads((OUT / 'primary' / 'results.json').read_text())
        decision = select_robust_configuration(primary, result, protocol['decision_rule'])
        (OUT / 'decision.json').write_text(json.dumps(decision, indent=2)+'\n')
        print(json.dumps(decision, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['primary', 'secondary'], required=True)
    main(parser.parse_args().stage)
