# Generated with an AI assistant. Independent standard-library recency check.
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main(root):
    processed, reports = root / 'data' / 'processed', root / 'reports'
    cutoff = datetime(2020, 5, 18, tzinfo=ZoneInfo('Europe/Kyiv')).timestamp()
    candidates = set(json.loads((processed / 'validation_candidates.json').read_text()))
    counts = defaultdict(Counter)
    with (processed / 'train_interactions.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            counts[row['user_id']][int(row['tv_show_id'])] = int(row['qualified_airings'])
    popularity = Counter(item for history in counts.values() for item in history)
    fallback = sorted(candidates, key=lambda item: (-popularity[item], item))[:5]
    weighted = defaultdict(Counter)
    events = 0
    with (processed / 'training_airings.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            end = int(row['airing_end_epoch'])
            assert end <= cutoff
            weighted[row['user_id']][int(row['tv_show_id'])] += 0.5 ** ((cutoff - end) / (28 * 86400))
            events += 1
    validation = defaultdict(Counter)
    with (processed / 'validation_interactions.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            validation[row['user_id']][int(row['tv_show_id'])] = int(row['qualified_airings'])
    targets = {user: set(sorted(items, key=lambda item: (-items[item], item))[:5])
               for user, items in validation.items()}
    checked, aps = 0, []
    maximum_error = 0.0
    with (reports / 'recency_predictions.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            user = row['user_id']
            scores = weighted[user]
            expected = sorted((item for item in scores if item in candidates),
                              key=lambda item: (-scores[item], -popularity[item], item))[:5]
            for item in fallback:
                if len(expected) == 5:
                    break
                if item not in expected:
                    expected.append(item)
            actual = list(map(int, row['tv_show_id'].split()))
            assert actual == expected, user
            checked += 1
            if user in targets:
                hits, score = 0, 0.0
                for rank, item in enumerate(actual, 1):
                    if item in targets[user]:
                        hits += 1
                        score += hits / rank
                ap = score / len(targets[user])
                maximum_error = max(maximum_error, abs(ap - float(row['ap_at_5'])))
                aps.append(ap)
    result = {'training_events': events, 'rankings_verified': checked,
              'evaluated_users': len(aps), 'map_at_5': sum(aps) / len(aps),
              'maximum_per_user_ap_difference': maximum_error}
    reported = json.loads((reports / 'recency_results.json').read_text())
    assert abs(result['map_at_5'] - reported['primary_comparison']['recency_map_at_5']) < 1e-12
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
