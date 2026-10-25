"""Diagnose personal-frequency failures without fitting another model.

Run after prepare_validation.py, which now also exports training_airings.csv.
The proposed experiment uses a fixed 28-day recency half-life, not a grid search.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from prepare_validation import CUTOFF

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / 'data' / 'processed'
REPORTS = ROOT / 'reports'
DAY = 86400
HALF_LIFE_DAYS = 28


def read_counts(filename):
    counts = defaultdict(Counter)
    with (PROCESSED / filename).open(newline='') as f:
        for row in csv.DictReader(f):
            counts[row['user_id']][int(row['tv_show_id'])] = int(row['qualified_airings'])
    return dict(counts)


def main():
    train = read_counts('train_interactions.csv')
    validation = read_counts('validation_interactions.csv')
    latest = defaultdict(dict)
    events = Counter()
    recent = defaultdict(Counter)
    with (PROCESSED / 'training_airings.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            user, item, end = row['user_id'], int(row['tv_show_id']), int(row['airing_end_epoch'])
            assert end <= CUTOFF
            latest[user][item] = max(latest[user].get(item, 0), end)
            events[user, item] += 1
            if end > CUTOFF-28*DAY:
                recent[user][item] += 1
    assert events == Counter({(u, i): n for u, h in train.items() for i, n in h.items()})
    targets = {}
    with (REPORTS / 'validation_targets.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            targets[row['user_id']] = set(map(int, row['target_ids'].split()))
    predictions, per_user_ap = {}, {}
    with (REPORTS / 'validation_predictions.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            if row['method'] == 'personal_frequency':
                predictions[row['user_id']] = list(map(int, row['tv_show_id'].split()))
                if row['ap_at_5']:
                    per_user_ap[row['user_id']] = float(row['ap_at_5'])
    categories = Counter()
    hit_counts = Counter()
    false_positives = Counter()
    age = defaultdict(Counter)
    users_with_stale_recommendations = set()
    for user, relevant in targets.items():
        recs, history = predictions[user], train.get(user, {})
        hit_counts[len(set(recs) & relevant)] += 1
        for item in relevant-set(recs):
            categories['known_item_below_top5' if item in history else 'no_qualified_training_view'] += 1
        for item in recs:
            hit = item in relevant
            if item in history:
                age_days = (CUTOFF-latest[user][item])/DAY
                bucket = 'last_seen_over_28_days_ago' if age_days > 28 else 'last_seen_within_28_days'
                age[bucket]['recommended_slots'] += 1
                age[bucket]['top5_hits'] += hit
                age[bucket]['any_validation_watch'] += validation[user].get(item, 0) > 0
                if age_days > 28:
                    users_with_stale_recommendations.add(user)
            else:
                age['popularity_fallback']['recommended_slots'] += 1
                age['popularity_fallback']['top5_hits'] += hit
                age['popularity_fallback']['any_validation_watch'] += validation[user].get(item, 0) > 0
            if not hit:
                false_positives['watched_but_outside_validation_top5' if validation[user].get(item, 0) else 'no_qualified_validation_watch'] += 1
    age_output = {bucket: dict(c, top5_hit_fraction=c['top5_hits']/c['recommended_slots'],
        any_validation_watch_fraction=c['any_validation_watch']/c['recommended_slots']) for bucket, c in age.items()}
    hashes = {name: hashlib.sha256((PROCESSED / name).read_bytes()).hexdigest() for name in
              ['train_interactions.csv', 'validation_interactions.csv', 'validation_candidates.json', 'training_airings.csv']}
    result = {'evaluated_users': len(targets), 'hits_per_user_distribution': dict(sorted(hit_counts.items())),
        'missed_target_categories': dict(categories), 'false_positive_categories': dict(false_positives),
        'recommendation_recency': age_output,
        'users_with_stale_recommendations': len(users_with_stale_recommendations),
        'map_for_users_with_stale_recommendations': sum(per_user_ap[u] for u in users_with_stale_recommendations)/len(users_with_stale_recommendations),
        'hypothesis': 'Old favourites may displace recently watched items; association is diagnostic, not causal evidence.',
        'one_proposed_improvement': {'name': 'recency_weighted_personal_frequency', 'half_life_days': HALF_LIFE_DAYS,
            'score': 'sum(2 ** (-(cutoff_epoch - airing_end_epoch) / (28 * 86400))) over qualified training airings',
            'reason': 'Four-week half-life retains weekly habits while reducing older evidence.',
            'selection': 'One manually fixed setting after baseline error analysis; no half-life grid search.',
            'unchanged': ['Split', 'Targets', 'Candidate IDs', 'Repeat policy', 'Training-popularity fallback', 'Tie breakers']},
        'input_sha256': hashes}
    (REPORTS / 'personal_frequency_errors.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
