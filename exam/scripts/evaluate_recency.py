"""Shared evaluation runner for recency weighting and popularity pseudo-counts.

Training uses only qualified training airings. All other policies are unchanged.
Each experiment uses one fixed parameter setting, not a grid search. The default
recency experiment failed; evaluate_smoothing.py runs the subsequent extension.
"""
import csv
import hashlib
import json
import platform
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from analyze_frequency_errors import HALF_LIFE_DAYS, read_counts
from compare_methods import average_precision_at_5, bootstrap_difference
from prepare_validation import BEGIN, CUTOFF

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / 'data' / 'processed'
REPORTS = ROOT / 'reports'
DAY = 86400


def recency_weight(airing_end, cutoff, half_life_days=HALF_LIFE_DAYS):
    if half_life_days <= 0 or airing_end > cutoff:
        raise ValueError('Require a positive half-life and no future training event.')
    return 2 ** (-(cutoff-airing_end)/(half_life_days*DAY))


def rank_history(scores, candidates, popularity):
    selected = sorted((i for i in scores if i in candidates and scores[i] > 0),
                      key=lambda i: (-scores[i], -popularity[i], i))[:5]
    fill = 5-len(selected)
    for item in sorted(candidates, key=lambda i: (-popularity[i], i)):
        if len(selected) == 5:
            break
        if item not in selected:
            selected.append(item)
    return selected, fill


def smoothed_scores(personal_counts, bonuses):
    result = Counter(personal_counts)
    result.update(bonuses)
    return result


def main(variant='recency'):
    if variant not in ('recency', 'smoothed'):
        raise ValueError(variant)
    prefix = variant
    method_name = variant+'_personal_frequency'
    began = time.perf_counter()
    users = json.loads((PROCESSED / 'all_users.json').read_text())
    candidates = set(json.loads((PROCESSED / 'validation_candidates.json').read_text()))
    train = read_counts('train_interactions.csv')
    popularity = Counter(i for history in train.values() for i in history)
    start = time.perf_counter()
    scores, latest, counts = defaultdict(Counter), defaultdict(dict), Counter()
    with (PROCESSED / 'training_airings.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            user, item = row['user_id'], int(row['tv_show_id'])
            a, b = int(row['airing_start_epoch']), int(row['airing_end_epoch'])
            assert BEGIN <= a < b <= CUTOFF
            if variant == 'recency':
                scores[user][item] += recency_weight(b, CUTOFF)
            latest[user][item] = max(latest[user].get(item, 0), b)
            counts[user, item] += 1
    assert counts == Counter({(u, i): n for u, h in train.items() for i, n in h.items()})
    if variant == 'smoothed':
        maximum = max(popularity[i] for i in candidates)
        bonuses = {item: 3*popularity[item]/maximum for item in candidates if popularity[item]}
    fit_seconds = time.perf_counter()-start
    start = time.perf_counter()
    predictions, fills = {}, {}
    for user in users:
        if user not in train:
            user_scores = {}
        elif variant == 'smoothed':
            user_scores = smoothed_scores(train[user], bonuses)
        else:
            user_scores = scores.get(user, {})
        predictions[user], fills[user] = rank_history(user_scores, candidates, popularity)
        assert len(set(predictions[user])) == len(predictions[user]) == 5
    predict_seconds = time.perf_counter()-start
    # All predictions are now fixed; held-out behaviour enters evaluation only.
    validation = read_counts('validation_interactions.csv')
    targets = {u: sorted(history, key=lambda i: (-history[i], i))[:5] for u, history in validation.items()}
    old, old_ap = {}, {}
    with (REPORTS / 'validation_predictions.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            if row['method'] == 'personal_frequency':
                old[row['user_id']] = list(map(int, row['tv_show_id'].split()))
                if row['ap_at_5']:
                    old_ap[row['user_id']] = float(row['ap_at_5'])
    assert set(old) == set(users)
    evaluated = [u for u in users if u in targets]
    ap = {u: average_precision_at_5(predictions[u], set(targets[u])) for u in evaluated}
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template = {row['user_id'] for row in csv.DictReader(f)}
    stale_users = {u for u in evaluated if any(i in train.get(u, {}) and CUTOFF-latest[u][i] > 28*DAY for i in old[u])}
    segments = {
        'all_target_users': evaluated,
        'five_target_users': [u for u in evaluated if len(targets[u]) == 5],
        'template_target_users': [u for u in evaluated if u in template],
        'warm_target_users': [u for u in evaluated if u in train],
        'cold_target_users': [u for u in evaluated if u not in train],
        'light_history_target_users': [u for u in evaluated if 0 < sum(train.get(u, {}).values()) <= 10],
        'heavy_history_target_users': [u for u in evaluated if sum(train.get(u, {}).values()) >= 100],
        'baseline_has_stale_recommendation': [u for u in evaluated if u in stale_users]}
    metrics = []
    for segment, members in segments.items():
        for method, recommendations, aps in [('personal_frequency', old, old_ap), (method_name, predictions, ap)]:
            hits = [len(set(recommendations[u]) & set(targets[u])) for u in members]
            metrics.append({'segment': segment, 'method': method, 'users': len(members),
                'map_at_5': sum(aps[u] for u in members)/len(members),
                'precision_at_5': sum(hits)/(5*len(members)),
                'recall_at_5': sum(h/len(targets[u]) for h, u in zip(hits, members))/len(members),
                'hit_rate_at_5': sum(h > 0 for h in hits)/len(members)})
    with (REPORTS / f'{prefix}_metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    with (REPORTS / f'{prefix}_predictions.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'tv_show_id', 'fallback_slots', 'ap_at_5', 'baseline_ap_at_5', 'ap_delta'])
        for user in users:
            writer.writerow([user, ' '.join(map(str, predictions[user])), fills[user], ap.get(user, ''),
                             old_ap.get(user, ''), ap[user]-old_ap[user] if user in ap else ''])
    deltas = {u: ap[u]-old_ap[u] for u in evaluated}
    outcome = Counter('improved' if d > 1e-12 else 'worsened' if d < -1e-12 else 'unchanged' for d in deltas.values())
    relevant_additions = sum(len((set(predictions[u])-set(old[u])) & set(targets[u])) for u in evaluated)
    relevant_removals = sum(len((set(old[u])-set(predictions[u])) & set(targets[u])) for u in evaluated)
    old_stale = sum(i in train.get(u, {}) and CUTOFF-latest[u][i] > 28*DAY for u in evaluated for i in old[u])
    new_stale = sum(i in train.get(u, {}) and CUTOFF-latest[u][i] > 28*DAY for u in evaluated for i in predictions[u])
    for user in users:
        assert set(predictions[user]) <= candidates
        expected = old[user] if user not in train else None
        if expected is not None:
            assert predictions[user] == expected
    comparison = bootstrap_difference([ap[u] for u in evaluated], [old_ap[u] for u in evaluated])
    fixed_examples = json.loads((REPORTS / 'validation_examples.json').read_text())
    chosen = [(e['label'], e['user_id'], 'Previously fixed training-volume example.') for e in fixed_examples]
    chosen += [('largest_gain', max(evaluated, key=lambda u: (deltas[u], -int(u))), 'Outcome-selected diagnostic: largest AP gain; not a representative sample.'),
               ('largest_loss', min(evaluated, key=lambda u: (deltas[u], int(u))), 'Outcome-selected diagnostic: largest AP loss; not a representative sample.')]
    display = json.loads((PROCESSED / 'display_metadata.json').read_text())
    examples = []
    for label, user, selection in chosen:
        def describe(item):
            end = latest.get(user, {}).get(item)
            return {'tv_show_id': item, **display[str(item)],
                'training_count': train.get(user, {}).get(item, 0),
                prefix+'_score': (scores.get(user, {}).get(item, 0.0) if variant == 'recency'
                                  else train.get(user, {}).get(item, 0)+bonuses.get(item, 0)),
                'days_since_last_qualified_training_airing': (CUTOFF-end)/DAY if end else None,
                'validation_count': validation.get(user, {}).get(item, 0),
                'validation_top5_hit': item in targets[user]}
        examples.append({'label': label, 'user_id': user, 'selection': selection,
            'baseline_ap_at_5': old_ap[user], prefix+'_ap_at_5': ap[user], 'ap_delta': deltas[user],
            'targets': [describe(i) for i in targets[user]],
            'baseline_top5': [describe(i) for i in old[user]], prefix+'_top5': [describe(i) for i in predictions[user]]})
    (REPORTS / f'{prefix}_examples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2)+'\n')
    baseline_map, recency_map = metrics[0]['map_at_5'], metrics[1]['map_at_5']
    parameters = ({'half_life_days': HALF_LIFE_DAYS,
                   'parameter_selection': 'Fixed 28-day half-life; no half-life grid search.'}
                  if variant == 'recency' else
                  {'popularity_bonus_maximum': 3,
                   'score': 'personal_airing_count + 3 * item_training_viewers / maximum_candidate_training_viewers',
                   'parameter_selection': 'Fixed maximum three-view bonus after the unsuccessful recency experiment; no coefficient grid search.'})
    result = {'change': ('Exponential recency weighting of qualified personal training airings only.' if variant == 'recency'
                        else 'Add up to three pseudo-views proportional to training item popularity to raw personal frequency.'),
        'parameters': parameters,
        'split_and_label_policy': 'Identical to the original validation experiment.',
        'known_holdout_warning': 'Error analysis and improvement choice use the known hold-out. This is model-selection evidence, not an untouched final estimate.',
        'metrics': metrics, 'primary_comparison': dict(comparison,
            baseline_map_at_5=baseline_map, **{prefix+'_map_at_5': recency_map},
            relative_map_change=recency_map/baseline_map-1),
        'user_outcomes': dict(outcome),
        'target_items_added_to_lists': relevant_additions, 'target_items_removed_from_lists': relevant_removals,
        'stale_recommended_slots_before': old_stale, 'stale_recommended_slots_after': new_stale,
        'unchanged_membership_users': sum(set(old[u]) == set(predictions[u]) for u in evaluated),
        'unchanged_ordered_lists_users': sum(old[u] == predictions[u] for u in evaluated),
        'fixed_inputs_sha256': {name: hashlib.sha256((REPORTS / name).read_bytes()).hexdigest() for name in ['validation_targets.csv', 'validation_predictions.csv', 'validation_metrics.csv']},
        'training_events_sha256': hashlib.sha256((PROCESSED / 'training_airings.csv').read_bytes()).hexdigest(),
        'fit_seconds': fit_seconds, 'predict_seconds': predict_seconds,
        'runtime_seconds': time.perf_counter()-began,
        'peak_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_rss_units': 'bytes on macOS; KiB on Linux',
        'environment': {'python': sys.version, 'platform': platform.platform()}}
    (REPORTS / f'{prefix}_results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['primary_comparison', 'user_outcomes', 'target_items_added_to_lists',
        'target_items_removed_from_lists', 'stale_recommended_slots_before', 'stale_recommended_slots_after', 'runtime_seconds']}, indent=2))


if __name__ == '__main__':
    main()
