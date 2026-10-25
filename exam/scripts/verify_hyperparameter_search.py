"""Independent search audit: fold reconstruction, frozen shortlist and all metrics.

Does not import model, preparation, search or evaluation project code.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
OUT, DATA = ROOT / 'reports' / 'hyperparameter_search', ROOT / 'data' / 'processed'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_counts(path):
    rows = defaultdict(dict)
    with path.open(newline='') as f:
        for r in csv.DictReader(f):
            rows[r['user_id']][int(r['tv_show_id'])] = int(r['qualified_airings'])
    return dict(rows)


def load_predictions(path):
    with path.open(newline='') as f:
        return {r['user_id']: list(map(int, r['tv_show_id'].split())) for r in csv.DictReader(f)}


def timestamp(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=ZoneInfo('Europe/Kyiv')).timestamp())


def main():
    plan = json.loads((ROOT / 'reports' / 'hyperparameter_plan.json').read_text())
    primary = json.loads((OUT / 'primary' / 'results.json').read_text())
    secondary = json.loads((OUT / 'secondary' / 'results.json').read_text())
    frozen = json.loads((OUT / 'finalists.json').read_text())
    decision = json.loads((OUT / 'decision.json').read_text())
    assert len(plan['configurations']) == len({c['id'] for c in plan['configurations']}) == 20
    ids = {c['id'] for c in plan['configurations']}
    assert {r['id'] for r in primary['ranking']} == ids
    top = [r['id'] for r in sorted(primary['ranking'], key=lambda r: (-r['map_at_5'], r['id']))[:4]]
    assert top == frozen['top_four_primary_ids']
    expected_confirmation = list(dict.fromkeys(top+['frequency_bonus_3']))
    assert frozen['confirmation_ids'] == expected_confirmation
    assert {r['id'] for r in secondary['ranking']} == set(expected_confirmation)
    assert frozen['primary_ranking_sha256'] == sha(OUT / 'primary' / 'ranking.json')
    assert frozen['plan_sha256'] == primary['plan_sha256'] == secondary['plan_sha256'] == sha(ROOT / 'reports' / 'hyperparameter_plan.json')
    assert frozen['frozen_at_epoch'] < min(r['start_epoch'] for r in secondary['runs'])
    assert timestamp(plan['folds']['secondary']['end']) == timestamp(plan['folds']['primary']['cutoff'])
    original = json.loads((ROOT / 'reports' / 'collaborative_results.json').read_text())
    for name, digest in original['input_sha256'].items():
        assert primary['input_sha256'][name] == digest == sha(DATA / name)
    # The secondary full-file join must agree with an independent projection of
    # qualified primary-training airings into the earlier two windows.
    begin = timestamp(plan['folds']['secondary']['begin'])
    cutoff = timestamp(plan['folds']['secondary']['cutoff'])
    finish = timestamp(plan['folds']['secondary']['end'])
    expected = {'train': Counter(), 'validation': Counter()}
    with (DATA / 'training_airings.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            a, b = int(r['airing_start_epoch']), int(r['airing_end_epoch'])
            key = (r['user_id'], int(r['tv_show_id']))
            if begin <= a < b <= cutoff:
                expected['train'][key] += 1
            elif cutoff <= a < b <= finish:
                expected['validation'][key] += 1
    for period in expected:
        actual = read_counts(DATA / 'search_secondary' / (period+'_interactions.csv'))
        assert expected[period] == Counter({(u, i): n for u, h in actual.items() for i, n in h.items()})
    # Rebuild candidate IDs and CBF metadata from the secondary training schedule.
    meta = defaultdict(lambda: defaultdict(set))
    candidates = set()
    fields = ['tv_show_category', 'tv_show_genre_1', 'tv_show_genre_2', 'tv_show_genre_3',
              'year_of_production', 'director', 'actors']
    with (ROOT / 'data' / 'export_arh_11-20-final.csv').open(newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            item, duration = int(r['tv_show_id']), int(r['duration'])
            if not item or duration <= 0:
                continue
            value = r['start_time']
            a = timestamp(f'{value[6:10]}-{value[3:5]}-{value[:2]} {value[11:]}')
            b = a+duration
            if a < finish and b > cutoff:
                candidates.add(item)
            if begin <= a < cutoff:
                for field in fields:
                    value = r[field].strip()
                    if value:
                        meta[str(item)][field].add(value)
    expected_meta = {i: {field: sorted(values) for field, values in row.items()} for i, row in meta.items()}
    assert expected_meta == json.loads((DATA / 'search_secondary' / 'training_metadata.json').read_text())
    assert candidates == set(json.loads((DATA / 'search_secondary' / 'validation_candidates.json').read_text()))
    stage_checks = {}
    all_predictions = {}
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    for stage, result in [('primary', primary), ('secondary', secondary)]:
        fold = ROOT / plan['folds'][stage]['data_dir']
        for name, digest in result['input_sha256'].items():
            assert sha(fold / name) == digest
        train, validation = read_counts(fold / 'train_interactions.csv'), read_counts(fold / 'validation_interactions.csv')
        targets = {u: set(sorted(h, key=lambda i: (-h[i], i))[:5]) for u, h in validation.items()}
        users = json.loads((fold / 'all_users.json').read_text())
        evaluated = [u for u in users if u in targets]
        candidate_set = set(json.loads((fold / 'validation_candidates.json').read_text()))
        popularity = Counter(i for h in train.values() for i in h)
        fallback = sorted(candidate_set, key=lambda i: (-popularity[i], i))
        with (OUT / stage / 'targets.csv').open(newline='') as f:
            exported = {r['user_id']: set(map(int, r['tv_show_id'].split())) for r in csv.DictReader(f)}
        assert exported == targets
        cohorts = {'all_target_users': set(targets),
            'five_target_users': {u for u in targets if len(targets[u]) == 5},
            'template_target_users': set(targets) & template,
            'warm_target_users': set(targets) & set(train), 'cold_target_users': set(targets)-set(train),
            'light_history_target_users': {u for u in targets if 0 < sum(train.get(u, {}).values()) <= 10},
            'heavy_history_target_users': {u for u in targets if sum(train.get(u, {}).values()) >= 100}}
        predictions, aps = {}, {}
        rows_checked = 0
        for config in result['ranking']:
            key = config['id']
            predictions[key], aps[key] = {}, {}
            with (OUT / stage / key / 'scored_predictions.csv').open(newline='') as f:
                for r in csv.DictReader(f):
                    u = r['user_id']
                    assert u not in predictions[key]
                    ids_row = list(map(int, r['tv_show_id'].split()))
                    assert len(ids_row) == len(set(ids_row)) == 5 and set(ids_row) <= candidate_set and 0 not in ids_row
                    predictions[key][u] = ids_row
                    if u not in train:
                        assert ids_row == fallback[:5] and int(r['fallback_slots']) == 5
                    if u in targets:
                        ranks = [rank for rank, i in enumerate(ids_row, 1) if i in targets[u]]
                        value = sum(n/rank for n, rank in enumerate(ranks, 1))/len(targets[u])
                        aps[key][u] = value
                        assert math.isclose(value, float(r['ap_at_5']), abs_tol=1e-12)
                    else:
                        assert r['ap_at_5'] == ''
                    rows_checked += 1
            assert set(predictions[key]) == set(users)
            assert predictions[key] == load_predictions(OUT / stage / key / 'predictions.csv')
            if config['family'] == 'frequency':
                maximum = max(popularity[i] for i in candidate_set)
                for u in users:
                    scores = {i: train.get(u, {}).get(i, 0)+config['bonus']*popularity[i]/maximum for i in candidate_set} if u in train else {}
                    wanted = sorted((i for i in candidate_set if scores.get(i, 0) > 0), key=lambda i: (-scores[i], -popularity[i], i))[:5]
                    wanted += [i for i in fallback if i not in wanted][:5-len(wanted)]
                    assert predictions[key][u] == wanted
        predictions['popularity_reference'] = {u: fallback[:5] for u in users}
        aps['popularity_reference'] = {}
        for u in targets:
            ranks = [rank for rank, i in enumerate(fallback[:5], 1) if i in targets[u]]
            aps['popularity_reference'][u] = sum(n/rank for n, rank in enumerate(ranks, 1))/len(targets[u])
        metric_rows = 0
        with (OUT / stage / 'metrics.csv').open(newline='') as f:
            for r in csv.DictReader(f):
                key, members = r['config_id'], cohorts[r['segment']]
                assert len(members) == int(r['users'])
                hits = {u: len(set(predictions[key][u]) & targets[u]) for u in members}
                expected_values = {'map_at_5': sum(aps[key][u] for u in members)/len(members),
                    'precision_at_5': sum(hits.values())/(5*len(members)),
                    'recall_at_5': sum(hits[u]/len(targets[u]) for u in members)/len(members),
                    'hit_rate_at_5': sum(h > 0 for h in hits.values())/len(members)}
                assert all(math.isclose(v, float(r[k]), abs_tol=1e-12) for k, v in expected_values.items())
                metric_rows += 1
        assert [r['id'] for r in result['ranking']] == sorted((c['id'] for c in result['ranking']), key=lambda k: (-sum(aps[k].values())/len(targets), k))
        # Reproduce finalist intervals, independently of the evaluation helper.
        for key in frozen['confirmation_ids']:
            rng = np.random.default_rng(42)
            delta = np.array([aps[key][u]-aps['frequency_bonus_3'][u] for u in evaluated])
            means = [float(delta[rng.integers(0, len(delta), len(delta))].mean()) for _ in range(2000)]
            interval = np.quantile(means, [.025, .975])
            saved = result['comparisons_vs_reference'][key]
            np.testing.assert_allclose(interval, saved['paired_bootstrap_95_percent_interval'], atol=1e-12)
            assert math.isclose(float(delta.mean()), saved['mean_delta'], abs_tol=1e-12)
        endpoints = sorted([(r['start_epoch'], 1) for r in result['runs']]+[(r['end_epoch'], -1) for r in result['runs']], key=lambda v: (v[0], v[1]))
        active = maximum_active = 0
        for _, change in endpoints:
            active += change; maximum_active = max(maximum_active, active)
        assert maximum_active == result['maximum_observed_concurrent_runs'] >= 2
        assert all(r['blas_threads'] == 1 for r in result['runs'])
        stage_checks[stage] = {'configuration_runs': len(result['ranking']), 'prediction_rows_checked': rows_checked,
            'cohort_metric_rows_recomputed': metric_rows, 'max_concurrent_runs_verified': maximum_active,
            'distinct_worker_pids': len(result['worker_pids'])}
        all_predictions[stage] = predictions
    # Existing settings must reproduce their previous forecasts exactly.
    known = {}
    with (ROOT / 'reports' / 'validation_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            mapped = {'personal_frequency': 'frequency_bonus_0', 'cbf': 'cbf_log', 'association_rules': 'association_rules_log'}.get(r['method'])
            if mapped:
                known.setdefault(mapped, {})[r['user_id']] = list(map(int, r['tv_show_id'].split()))
    known['frequency_bonus_3'] = load_predictions(ROOT / 'reports' / 'smoothed_predictions.csv')
    with (ROOT / 'reports' / 'repeat_aware_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            mapped = {'ppr_raw_counts': 'ppr_d085_raw', 'personalized_pagerank': 'ppr_d085_log',
                'als_log_counts_weighted': 'mf_f32_r01_a20', 'als_log_counts_uniform': 'mf_f32_r01_a0'}.get(r['method'])
            if mapped:
                known.setdefault(mapped, {})[r['user_id']] = list(map(int, r['tv_show_id'].split()))
    for key, reference in known.items():
        assert all_predictions['primary'][key] == reference
    assert all_predictions['primary']['frequency_bonus_1'] == all_predictions['primary']['frequency_bonus_0']
    eligible = []
    for key in frozen['confirmation_ids']:
        d1 = primary['comparisons_vs_reference'][key]['mean_delta']
        d2 = secondary['comparisons_vs_reference'][key]['mean_delta']
        low = secondary['comparisons_vs_reference'][key]['paired_bootstrap_95_percent_interval'][0]
        if d1 > 0 and d2 > 0 and low > 0:
            score = next(r['map_at_5'] for r in primary['ranking'] if r['id'] == key)
            eligible.append((min(d1, d2), score, key))
    eligible.sort(key=lambda r: (-r[0], -r[1], r[2]))
    selected = eligible[0][2] if eligible else 'frequency_bonus_3'
    assert selected == decision['selected_config_id']
    report = {'status': 'passed', 'unique_configurations': 20,
        'total_fit_runs': len(primary['runs'])+len(secondary['runs']),
        'secondary_shortlist_frozen_before_runs': True,
        'original_inputs_unchanged': True, 'secondary_counts_rebuilt_from_original_training_events': True,
        'secondary_qualified_training_airings_reconciled': sum(expected['train'].values()),
        'secondary_qualified_validation_airings_reconciled': sum(expected['validation'].values()),
        'secondary_metadata_and_candidates_independently_rebuilt': True,
        'validation_periods_disjoint': True, 'stages': stage_checks,
        'previous_configurations_reproduced_exactly': sorted(known),
        'bonus_0_and_1_predictions_identical': True, 'selected_config_id_independently_verified': selected,
        'artifact_sha256': {str(p.relative_to(OUT)): sha(p) for p in [OUT / 'primary' / 'ranking.json', OUT / 'secondary' / 'ranking.json', OUT / 'finalists.json', OUT / 'decision.json']}}
    (ROOT / 'reports' / 'hyperparameter_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()
