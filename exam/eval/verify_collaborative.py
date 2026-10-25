# Generated with an AI assistant. Independent standard-library MAP@5 check.
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main(root, prefix='collaborative'):
    data, reports = root / 'data' / 'processed', root / 'reports'
    counts = defaultdict(Counter)
    with (data / 'validation_interactions.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            counts[row['user_id']][int(row['tv_show_id'])] = int(row['qualified_airings'])
    targets = {user: set(sorted(history, key=lambda item: (-history[item], item))[:5])
               for user, history in counts.items()}
    with (root / 'data' / 'submission.csv').open(newline='') as stream:
        template = {row['user_id'] for row in csv.DictReader(stream)}
    candidates = set(json.loads((data / 'validation_candidates.json').read_text()))
    sums, sizes, checked = defaultdict(float), Counter(), Counter()
    maximum_ap_error = 0.0
    checked_per_user_aps = 0
    with (reports / f'{prefix}_predictions.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            user, method = row['user_id'], row.get('method', 'history_schedule_ranker')
            prediction = list(map(int, row['tv_show_id'].split()))
            assert len(prediction) == len(set(prediction)) == 5
            assert set(prediction) <= candidates and 0 not in prediction
            checked[method] += 1
            if user not in targets:
                continue
            relevant = targets[user]
            hits, score = 0, 0.0
            for rank, item in enumerate(prediction, 1):
                if item in relevant:
                    hits += 1
                    score += hits / rank
            ap = score / len(relevant)
            if row.get('ap_at_5') is not None:
                maximum_ap_error = max(maximum_ap_error, abs(ap - float(row['ap_at_5'])))
                checked_per_user_aps += 1
            segments = ['all_target_users']
            if len(relevant) == 5:
                segments.append('five_target_users')
            if user in template:
                segments.append('template_target_users')
            for segment in segments:
                sums[segment, method] += ap
                sizes[segment, method] += 1
    with (reports / f'{prefix}_metrics.csv').open(newline='') as stream:
        reported = {(row['segment'], row['method']): float(row['map_at_5'])
                    for row in csv.DictReader(stream)}
    metrics = []
    for (segment, method), total in sorted(sums.items()):
        value = total / sizes[segment, method]
        assert abs(value - reported[segment, method]) < 1e-12
        metrics.append({'segment': segment, 'method': method,
                        'users': sizes[segment, method], 'map_at_5': value})
    print(json.dumps({'rankings_checked': dict(checked),
                      'per_user_ap_comparisons': checked_per_user_aps,
                      'maximum_per_user_ap_difference': maximum_ap_error if checked_per_user_aps else None,
                      'metrics': metrics}, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'collaborative')
