"""Independently rebuild all extension ranks and MAP values using standard Python.

Does not import either modelling or evaluation implementation.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA, REPORTS = ROOT / 'data' / 'processed', ROOT / 'reports'


def main():
    cutoff = int(datetime(2020, 5, 18, tzinfo=ZoneInfo('Europe/Kyiv')).timestamp())
    train = defaultdict(dict)
    with (DATA / 'train_interactions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            train[r['user_id']][int(r['tv_show_id'])] = int(r['qualified_airings'])
    popularity = Counter(i for history in train.values() for i in history)
    candidates = set(json.loads((DATA / 'validation_candidates.json').read_text()))
    users = set(json.loads((DATA / 'all_users.json').read_text()))
    pop_order = sorted(candidates, key=lambda i: (-popularity[i], i))
    maximum = max(popularity[i] for i in candidates)
    recency = defaultdict(Counter)
    latest = defaultdict(dict)
    event_counts = Counter()
    with (DATA / 'training_airings.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            u, i, end = r['user_id'], int(r['tv_show_id']), int(r['airing_end_epoch'])
            assert end <= cutoff
            recency[u][i] += pow(2., -(cutoff-end)/(28*86400))
            latest[u][i] = max(latest[u].get(i, 0), end)
            event_counts[u, i] += 1
    assert event_counts == Counter({(u, i): n for u, h in train.items() for i, n in h.items()})
    targets = {}
    with (REPORTS / 'validation_targets.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            targets[r['user_id']] = set(map(int, r['target_ids'].split()))
    old, old_ap = {}, {}
    with (REPORTS / 'validation_predictions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            if r['method'] == 'personal_frequency':
                old[r['user_id']] = list(map(int, r['tv_show_id'].split()))
                if r['ap_at_5']:
                    old_ap[r['user_id']] = float(r['ap_at_5'])
    original_hashes = json.loads((REPORTS / 'validation_verification.json').read_text())['artifact_sha256']
    for name, digest in original_hashes.items():
        assert hashlib.sha256((REPORTS / name).read_bytes()).hexdigest() == digest
    reports = {}
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    cohorts = {
        'all_target_users': set(targets),
        'five_target_users': {u for u in targets if len(targets[u]) == 5},
        'template_target_users': set(targets) & template,
        'warm_target_users': set(targets) & set(train),
        'cold_target_users': set(targets)-set(train),
        'light_history_target_users': {u for u in targets if 0 < sum(train.get(u, {}).values()) <= 10},
        'heavy_history_target_users': {u for u in targets if sum(train.get(u, {}).values()) >= 100},
        'baseline_has_stale_recommendation': {u for u in targets if any(i in train.get(u, {}) and cutoff-latest[u][i] > 28*86400 for i in old[u])}}
    for variant in ['recency', 'smoothed']:
        seen, ap, predictions = set(), {}, {}
        with (REPORTS / f'{variant}_predictions.csv').open(newline='') as f:
            for r in csv.DictReader(f):
                u = r['user_id']
                assert u not in seen
                seen.add(u)
                ids = list(map(int, r['tv_show_id'].split()))
                predictions[u] = ids
                if u not in train:
                    expected = pop_order[:5]
                    assert ids == old[u] and int(r['fallback_slots']) == 5
                else:
                    def score(i):
                        return (recency[u].get(i, 0) if variant == 'recency'
                                else train[u].get(i, 0)+3*popularity[i]/maximum)
                    positive = [i for i in candidates if score(i) > 0]
                    expected = sorted(positive, key=lambda i: (-score(i), -popularity[i], i))[:5]
                    assert int(r['fallback_slots']) == 5-len(expected)
                    expected += [i for i in pop_order if i not in expected][:5-len(expected)]
                assert ids == expected and len(ids) == len(set(ids)) == 5 and set(ids) <= candidates
                if u in targets:
                    ranks = [rank for rank, i in enumerate(ids, 1) if i in targets[u]]
                    value = sum(n/rank for n, rank in enumerate(ranks, 1))/len(targets[u])
                    assert math.isclose(value, float(r['ap_at_5']), abs_tol=1e-12)
                    assert math.isclose(value-old_ap[u], float(r['ap_delta']), abs_tol=1e-12)
                    ap[u] = value
                else:
                    assert r['ap_at_5'] == r['ap_delta'] == ''
        assert seen == users and set(ap) == set(targets)
        result = json.loads((REPORTS / f'{variant}_results.json').read_text())
        primary = sum(ap.values())/len(ap)
        assert math.isclose(primary, result['primary_comparison'][variant+'_map_at_5'], abs_tol=1e-12)
        outcomes = Counter('improved' if ap[u]-old_ap[u] > 1e-12 else 'worsened' if ap[u]-old_ap[u] < -1e-12 else 'unchanged' for u in ap)
        assert outcomes == result['user_outcomes']
        metric_rows = 0
        with (REPORTS / f'{variant}_metrics.csv').open(newline='') as f:
            for row in csv.DictReader(f):
                members = cohorts[row['segment']]
                assert int(row['users']) == len(members)
                ps, aps = (old, old_ap) if row['method'] == 'personal_frequency' else (predictions, ap)
                hits = {u: len(set(ps[u]) & targets[u]) for u in members}
                expected_metrics = {
                    'map_at_5': sum(aps[u] for u in members)/len(members),
                    'precision_at_5': sum(hits.values())/(5*len(members)),
                    'recall_at_5': sum(hits[u]/len(targets[u]) for u in members)/len(members),
                    'hit_rate_at_5': sum(h > 0 for h in hits.values())/len(members)}
                assert all(math.isclose(value, float(row[key]), abs_tol=1e-12) for key, value in expected_metrics.items())
                metric_rows += 1
        reports[variant] = {'prediction_rows_rebuilt': len(seen), 'per_user_ap_recomputed': len(ap),
                            'primary_map_at_5': primary, 'outcomes_recomputed': dict(outcomes),
                            'cohort_metric_rows_independently_recomputed': metric_rows}
    report = {'status': 'passed', 'original_artifact_hashes_unchanged': True,
              'training_airings_reconciled_with_original_counts': sum(event_counts.values()),
              'variants': reports,
              'new_artifact_sha256': {f'{v}_{name}.csv': hashlib.sha256((REPORTS / f'{v}_{name}.csv').read_bytes()).hexdigest()
                                      for v in ['recency', 'smoothed'] for name in ['predictions', 'metrics']}}
    (REPORTS / 'frequency_extension_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
