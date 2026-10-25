# Generated with an AI assistant. Independent standard-library search audit.
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main(root):
    reports = root / 'reports' / 'hyperparameter_search'
    plan = json.loads((root / 'reports' / 'hyperparameter_plan.json').read_text())
    configurations = {row['id'] for row in plan['configurations']}
    assert len(configurations) == 20
    result = {'unique_configurations': len(configurations), 'folds': {}}
    for fold, relative_data in [('primary', 'data/processed'),
                                ('secondary', 'data/processed/search_secondary')]:
        data = root / relative_data
        history = defaultdict(Counter)
        with (data / 'validation_interactions.csv').open(newline='') as stream:
            for row in csv.DictReader(stream):
                history[row['user_id']][int(row['tv_show_id'])] = int(row['qualified_airings'])
        targets = {user: set(sorted(items, key=lambda item: (-items[item], item))[:5])
                   for user, items in history.items()}
        candidates = set(json.loads((data / 'validation_candidates.json').read_text()))
        users = set(json.loads((data / 'all_users.json').read_text()))
        with (reports / fold / 'targets.csv').open(newline='') as stream:
            emitted = {row['user_id']: set(map(int, row['tv_show_id'].split()))
                       for row in csv.DictReader(stream)}
        assert targets == emitted
        with (reports / fold / 'metrics.csv').open(newline='') as stream:
            reported = {row['config_id']: float(row['map_at_5']) for row in csv.DictReader(stream)
                        if row['segment'] == 'all_target_users' and row['config_id'] != 'popularity_reference'}
        checked = []
        for config, stated_map in reported.items():
            assert config in configurations
            seen, scores = set(), []
            with (reports / fold / config / 'predictions.csv').open(newline='') as stream:
                for row in csv.DictReader(stream):
                    user = row['user_id']
                    assert user not in seen
                    seen.add(user)
                    prediction = list(map(int, row['tv_show_id'].split()))
                    assert len(prediction) == len(set(prediction)) == 5
                    assert set(prediction) <= candidates and 0 not in prediction
                    if user not in targets:
                        continue
                    hits, numerator = 0, 0.0
                    for rank, item in enumerate(prediction, 1):
                        if item in targets[user]:
                            hits += 1
                            numerator += hits / rank
                    scores.append(numerator / len(targets[user]))
            assert seen == users
            assert len(scores) == len(targets)
            value = sum(scores) / len(scores)
            assert abs(value - stated_map) < 1e-12
            checked.append({'config_id': config, 'rankings_checked': len(seen),
                            'evaluated_users': len(scores), 'map_at_5': value})
        checked.sort(key=lambda row: (-row['map_at_5'], row['config_id']))
        result['folds'][fold] = {'configurations_checked': len(checked), 'ranking': checked}
    assert result['folds']['primary']['configurations_checked'] == 20
    selected = json.loads((reports / 'decision.json').read_text())['selected_config_id']
    result['selected_config_id'] = selected
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
