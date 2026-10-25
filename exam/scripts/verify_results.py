# Generated with an AI assistant
"""Independently verify saved predictions, targets, metrics and sampled rules.

This script uses the standard library and does not import the modelling code.
Run: .venv/bin/python scripts/verify_results.py
"""
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
PROCESSED = ROOT / 'data' / 'processed'


def counts(filename):
    result = defaultdict(dict)
    with (PROCESSED / filename).open(newline='') as f:
        for row in csv.DictReader(f):
            result[row['user_id']][int(row['tv_show_id'])] = int(row['qualified_airings'])
    return result


def main():
    train, validation = counts('train_interactions.csv'), counts('validation_interactions.csv')
    candidates = set(json.loads((PROCESSED / 'validation_candidates.json').read_text()))
    users = set(json.loads((PROCESSED / 'all_users.json').read_text()))
    targets = {}
    with (OUT / 'validation_targets.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            u = row['user_id']
            target = list(map(int, row['target_ids'].split()))
            expected = sorted(validation[u], key=lambda i: (-validation[u][i], i))[:5]
            assert target == expected and set(target) <= candidates
            targets[u] = set(target)
    assert set(targets) == set(validation)
    prediction, ap = defaultdict(dict), defaultdict(dict)
    with (OUT / 'validation_predictions.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            u, method = row['user_id'], row['method']
            ids = list(map(int, row['tv_show_id'].split()))
            assert u not in prediction[method]
            assert len(ids) == len(set(ids)) == 5 and set(ids) <= candidates and 0 not in ids
            prediction[method][u] = ids
            if u in targets:
                relevant_ranks = [rank for rank, item in enumerate(ids, 1) if item in targets[u]]
                value = sum(hit_index/rank for hit_index, rank in enumerate(relevant_ranks, 1))/len(targets[u])
                ap[method][u] = value
                assert math.isclose(value, float(row['ap_at_5']), abs_tol=1e-12)
            else:
                assert row['ap_at_5'] == ''
    for method, predictions in prediction.items():
        assert set(predictions) == users
        for u in users-set(train):
            assert predictions[u] == prediction['popularity'][u]
    popularity = Counter(item for h in train.values() for item in h)
    pop_top = sorted(candidates, key=lambda i: (-popularity[i], i))[:5]
    assert all(p == pop_top for p in prediction['popularity'].values())
    for u in users:
        positive = sorted(set(train[u]) & candidates, key=lambda i: (-train[u][i], -popularity[i], i))[:5]
        for item in sorted(candidates, key=lambda i: (-popularity[i], i)):
            if len(positive) == 5:
                break
            if item not in positive:
                positive.append(item)
        assert prediction['personal_frequency'][u] == positive
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {r['user_id'] for r in csv.DictReader(f)}
    cohorts = {
        'all_target_users': set(targets),
        'five_target_users': {u for u in targets if len(targets[u]) == 5},
        'template_target_users': set(targets) & template,
        'warm_target_users': {u for u in targets if train[u]},
        'cold_target_users': {u for u in targets if not train[u]},
        'light_history_target_users': {u for u in targets if 0 < sum(train[u].values()) <= 10},
        'heavy_history_target_users': {u for u in targets if sum(train[u].values()) >= 100}}
    metric_rows = 0
    with (OUT / 'validation_metrics.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            cohort = cohorts[row['segment']]
            assert len(cohort) == int(row['users'])
            independently_computed = sum(ap[row['method']][u] for u in cohort)/len(cohort)
            assert math.isclose(independently_computed, float(row['map_at_5']), abs_tol=1e-12)
            metric_rows += 1
    viewers = defaultdict(set)
    for u, h in train.items():
        for item in h:
            viewers[item].add(u)
    # Reservoir sample: equal inclusion probability for every retained rule.
    rng = random.Random(42)
    sample, outgoing = [], Counter()
    with (OUT / 'association_rules.csv').open(newline='') as f:
        for n, row in enumerate(csv.DictReader(f), 1):
            a, b = int(row['antecedent_id']), int(row['consequent_id'])
            assert a != b and int(row['pair_users']) >= 3 and float(row['confidence']) >= .02
            outgoing[a] += 1
            if len(sample) < 100:
                sample.append(row)
            else:
                pos = rng.randrange(n)
                if pos < len(sample):
                    sample[pos] = row
    assert max(outgoing.values()) <= 100
    for row in sample:
        a, b = int(row['antecedent_id']), int(row['consequent_id'])
        support = len(viewers[a] & viewers[b])
        confidence = support/len(viewers[a])
        assert support == int(row['pair_users']) and len(viewers[a]) == int(row['antecedent_users'])
        assert math.isclose(confidence, float(row['confidence']), abs_tol=1e-12)
        assert math.isclose(confidence*support/(support+10), float(row['shrunk_confidence']), abs_tol=1e-12)
    hashes = {}
    for name in ['validation_predictions.csv', 'validation_targets.csv', 'validation_metrics.csv', 'association_rules.csv']:
        hashes[name] = hashlib.sha256((OUT / name).read_bytes()).hexdigest()
    report = {'status': 'passed', 'prediction_rows_checked': sum(map(len, prediction.values())),
              'target_users_checked': len(targets), 'metric_rows_independently_recomputed': metric_rows,
              'association_rules_checked_for_constraints': n,
              'association_rules_independently_recomputed': len(sample), 'sampling_seed': 42,
              'checks': ['Exactly five distinct nonzero candidate IDs per user and method.',
                         'Targets reconstructed from held-out counts.', 'All per-user AP values independently recomputed.',
                         'All segment MAP values independently recomputed.', 'Identical cold-start fallback.',
                         'All popularity and personal-frequency rankings independently recomputed.',
                         'Sampled rule supports and weights recomputed from training user sets.'],
              'artifact_sha256': hashes}
    (OUT / 'validation_verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
