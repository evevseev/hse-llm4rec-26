# Generated with an AI assistant. Independent standard-library metric check.
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main(root):
    processed = root / 'data' / 'processed'
    reports = root / 'reports'
    histories = {}
    for split in ['train', 'validation']:
        counts = defaultdict(Counter)
        with (processed / f'{split}_interactions.csv').open(newline='') as stream:
            for row in csv.DictReader(stream):
                counts[row['user_id']][int(row['tv_show_id'])] = int(row['qualified_airings'])
        histories[split] = counts
    train, validation = histories['train'], histories['validation']
    targets = {user: set(sorted(items, key=lambda item: (-items[item], item))[:5])
               for user, items in validation.items()}
    candidates = set(json.loads((processed / 'validation_candidates.json').read_text()))
    popularity = Counter()
    for items in train.values():
        popularity.update(items.keys())
    popular = sorted(candidates, key=lambda item: (-popularity[item], item))[:5]
    totals = defaultdict(float)
    populations = Counter()
    baseline_checks = Counter()
    maximum_ap_error = 0.0
    with (reports / 'validation_predictions.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            user, method = row['user_id'], row['method']
            prediction = list(map(int, row['tv_show_id'].split()))
            assert len(prediction) == len(set(prediction)) == 5
            assert set(prediction) <= candidates and 0 not in prediction
            if method == 'popularity':
                assert prediction == popular
                baseline_checks[method] += 1
            if method == 'personal_frequency':
                personal = sorted((item for item in train[user] if item in candidates),
                                  key=lambda item: (-train[user][item], -popularity[item], item))[:5]
                for item in popular:
                    if len(personal) == 5:
                        break
                    if item not in personal:
                        personal.append(item)
                assert prediction == personal
                baseline_checks[method] += 1
            if user not in targets:
                continue
            relevant = targets[user]
            hits = 0
            numerator = 0.0
            for rank, item in enumerate(prediction, 1):
                if item in relevant:
                    hits += 1
                    numerator += hits / rank
            ap = numerator / len(relevant)
            maximum_ap_error = max(maximum_ap_error, abs(ap - float(row['ap_at_5'])))
            for segment in ['all_target_users'] + (['five_target_users'] if len(relevant) == 5 else []):
                totals[segment, method] += ap
                populations[segment, method] += 1
    result = {'baseline_predictions_verified': dict(baseline_checks),
              'maximum_per_user_ap_difference': maximum_ap_error,
              'metrics': [{'segment': segment, 'method': method, 'users': populations[segment, method],
                           'map_at_5': total / populations[segment, method]}
                          for (segment, method), total in sorted(totals.items())]}
    with (reports / 'validation_metrics.csv').open(newline='') as stream:
        official = {(row['segment'], row['method']): float(row['map_at_5'])
                    for row in csv.DictReader(stream)}
    for row in result['metrics']:
        assert abs(row['map_at_5'] - official[row['segment'], row['method']]) < 1e-12
    smoothing_file = reports / 'smoothed_predictions.csv'
    if smoothing_file.exists():
        highest_popularity = max(popularity[item] for item in candidates)
        checked, aps = 0, []
        with smoothing_file.open(newline='') as stream:
            for row in csv.DictReader(stream):
                user = row['user_id']
                def score(item):
                    return train[user][item] + 3 * popularity[item] / highest_popularity
                expected = sorted(candidates, key=lambda item: (-score(item), -popularity[item], item))[:5]
                prediction = list(map(int, row['tv_show_id'].split()))
                assert prediction == expected, user
                checked += 1
                if user in targets:
                    hits, numerator = 0, 0.0
                    for rank, item in enumerate(prediction, 1):
                        if item in targets[user]:
                            hits += 1
                            numerator += hits / rank
                    ap = numerator / len(targets[user])
                    assert abs(ap - float(row['ap_at_5'])) < 1e-12
                    aps.append(ap)
        result['smoothing'] = {'rankings_verified': checked, 'evaluated_users': len(aps),
                               'map_at_5': sum(aps) / len(aps)}
        reported = json.loads((reports / 'smoothed_results.json').read_text())
        assert abs(result['smoothing']['map_at_5'] - reported['primary_comparison']['smoothed_map_at_5']) < 1e-12
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
