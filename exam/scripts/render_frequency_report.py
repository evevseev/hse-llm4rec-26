# Generated with an AI assistant
"""Render a transparent error-analysis report including the unsuccessful experiment."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from analyze_frequency_errors import read_counts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'


def load(name):
    return json.loads((OUT / name).read_text())


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def main():
    errors = load('personal_frequency_errors.json')
    recency, smoothed = load('recency_results.json'), load('smoothed_results.json')
    verification = load('frequency_extension_verification.json')
    tests = load('frequency_extension_tests.json')
    examples = load('smoothed_examples.json')
    original = load('validation_results.json')
    train = read_counts('train_interactions.csv')
    targets = {}
    with (OUT / 'validation_targets.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            targets[row['user_id']] = set(map(int, row['target_ids'].split()))
    before, after = {}, {}
    with (OUT / 'validation_predictions.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            if row['method'] == 'personal_frequency':
                before[row['user_id']] = list(map(int, row['tv_show_id'].split()))
    with (OUT / 'smoothed_predictions.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            after[row['user_id']] = list(map(int, row['tv_show_id'].split()))
    bins = defaultdict(Counter)
    added_target_types, removed_target_types = Counter(), Counter()
    for user, relevant in targets.items():
        for item in before[user]:
            count = train.get(user, {}).get(item, 0)
            bucket = '0 (fallback)' if count == 0 else '1–2' if count <= 2 else '3–5' if count <= 5 else '6–10' if count <= 10 else '>10'
            bins[bucket]['slots'] += 1
            bins[bucket]['target_hits'] += item in relevant
        for item in (set(after[user])-set(before[user])) & relevant:
            added_target_types['previously_observed' if item in train.get(user, {}) else 'no_qualified_training_view'] += 1
        for item in (set(before[user])-set(after[user])) & relevant:
            removed_target_types['previously_observed' if item in train.get(user, {}) else 'no_qualified_training_view'] += 1
    details = {'baseline_slots_by_personal_count': {k: dict(v, target_hit_fraction=v['target_hits']/v['slots']) for k, v in bins.items()},
               'smoothed_added_targets': dict(added_target_types), 'smoothed_removed_targets': dict(removed_target_types)}
    (OUT / 'personal_frequency_error_details.json').write_text(json.dumps(details, indent=2)+'\n')
    comparison = smoothed['primary_comparison']
    low, high = comparison['paired_bootstrap_95_percent_interval']
    missed = errors['missed_target_categories']
    lines = [
        '# Personal-frequency errors and a simple improvement', '',
        'Experiment date: 2026-10-25. All figures are offline validation results, not Kaggle or online measurements.', '',
        '## Executive result', '',
        f"**Keep raw personal viewing counts and add a small popularity pseudo-count: MAP@5 rises from {comparison['baseline_map_at_5']:.6f} to {comparison['smoothed_map_at_5']:.6f}.**",
        f"Absolute gain: {comparison['mean_delta']:.6f}; relative gain: {comparison['relative_map_change']:.2%}.",
        'The final extension is one explicit score formula, with no content model, graph or learned blending weight.', '',
        '**Exploration disclosure:** the first attempted improvement, 28-day recency weighting, reduced MAP@5. After observing this failure, a second fixed experiment added popularity smoothing.',
        'Both experiments are retained. No half-life or smoothing-coefficient grid search was run, but the two approaches were sequentially selected on the same known hold-out.', '',
        '## 1. What remains fixed', '',
        '- Training: March 9 to May 18, 2020 (weeks 11–20); validation: May 18 to July 27 (weeks 21–30), Europe/Kyiv.',
        '- Match channels and intervals; union fragments per user/airing; require >=80% of an airing. Exclude zero IDs and boundary-crossing airings.',
        '- Identical training counts, held-out labels, 6,384 candidate IDs, repeat policy and tie-breakers.',
        '- Primary MAP@5 uses the same 4,643 users with targets. Empty-target users are excluded exactly as before.',
        '- Cold users get the same training-popularity Top-5. Missing positions are filled from that same popularity list.',
        '- No validation viewing data enters the scores. Validation was already known when choosing these experiments, so their results are model-selection evidence.',
        '- Adding an export of training airing timestamps to preparation did not change the original predictions/targets/metrics, as checked by artifact hashes.', '',
        '## 2. Where raw personal frequency makes mistakes', '',
        '### Missed targets', '',
        f"There are {sum(missed.values()):,} missed user-target pairs:",
        f"- {missed['no_qualified_training_view']:,} ({missed['no_qualified_training_view']/sum(missed.values()):.2%}) have no qualified training view by that user. Raw frequency cannot score these above zero; only its fallback can introduce them.",
        f"- {missed['known_item_below_top5']:,} were observed in training but were ranked below the five selected items.",
        '“No qualified training view” does not mean the user has never seen the programme; it concerns only this observed platform history and our watch rule.', '',
        '### False positives', '',
        f"- {errors['false_positive_categories']['no_qualified_validation_watch']:,} recommended slots have no qualified validation watch.",
        f"- {errors['false_positive_categories']['watched_but_outside_validation_top5']:,} were actually watched, but fall outside the validation top five and are therefore metric misses.",
        'This distinction matters: a metric miss is not necessarily an irrelevant programme or evidence of dissatisfaction.', '',
        '| Baseline target hits per user | Users |', '|---:|---:|']
    for hits, users in errors['hits_per_user_distribution'].items():
        lines.append(f'| {hits} | {users:,} |')
    lines += ['', '### Reliability of weak versus repeated personal evidence', '',
              '| Personal training count of recommended item | Recommended slots | Target-hit fraction |', '|---|---:|---:|']
    for bucket in ['0 (fallback)', '1–2', '3–5', '6–10', '>10']:
        row = details['baseline_slots_by_personal_count'][bucket]
        lines.append(f"| {bucket} | {row['slots']:,} | {row['target_hit_fraction']:.2%} |")
    lines += ['', 'These are descriptive associations, not causal effects or independently calibrated confidence probabilities.', '',
              '### Why recency looked plausible', '',
              '| Latest personal training watch | Recommended slots | Validation Top-5 hit fraction | Any qualified validation watch |',
              '|---|---:|---:|---:|']
    for bucket in ['last_seen_over_28_days_ago', 'last_seen_within_28_days']:
        row = errors['recommendation_recency'][bucket]
        lines.append(f"| {bucket.replace('_', ' ')} | {row['recommended_slots']:,} | {row['top5_hit_fraction']:.2%} | {row['any_validation_watch_fraction']:.2%} |")
    lines += ['', '## 3. Unsuccessful first experiment: recency weighting', '',
        '`score(u,i) = sum(2 ** (-age_in_days / 28))` over qualified training airings of the item.',
        'Age is measured from airing end to the training cutoff, using elapsed seconds. A four-week half-life was fixed to retain weekly habits while reducing old evidence.',
        f"MAP@5 fell to **{recency['primary_comparison']['recency_map_at_5']:.6f}** ({recency['primary_comparison']['mean_delta']:+.6f} absolute).",
        f"The change added {recency['target_items_added_to_lists']} target items to lists but removed {recency['target_items_removed_from_lists']}; {recency['user_outcomes']['improved']} users improved and {recency['user_outcomes']['worsened']} worsened.",
        'It did remove stale favourites, but that alone was not an effective prediction rule for the next ten weeks. Recency correlations did not establish that discarding older frequency evidence would help.',
        'This experiment is rejected as the current recommendation strategy.', '',
        '## 4. Selected simple improvement: popularity pseudo-counts', '',
        '**Score:**', '',
        '`score(u,i) = personal_qualified_airing_count(u,i) + 3 * viewers_train(i) / max_candidate_viewers_train`.', '',
        '- `viewers_train(i)` counts distinct training users with a qualified view, matching the original popularity baseline.',
        '- The global favourite receives three pseudo-views; less popular items receive a proportionally smaller bonus.',
        '- Strong personal preferences are retained: an item more than three personal views ahead cannot be overtaken solely by this bounded bonus.',
        '- A globally popular item can enter even if the user has not watched it in the training window, instead of waiting until the personal list has fewer than five items.',
        '- Rank by score, then training popularity, then ascending ID. Allow repeats of previously watched programmes.',
        '- The maximum bonus of 3 was a manually fixed heuristic, not a selected best value from a sweep. No claim is made that it is optimal.',
        '- This is a documented fusion of personal counts and normalized training popularity, not a probability estimate.', '',
        '## 5. Quality comparison', '',
        '| Method | Primary MAP@5 |', '|---|---:|']
    for method in ['popularity', 'personal_frequency', 'cbf', 'association_rules']:
        row = next(r for r in original['metrics'] if r['segment'] == 'all_target_users' and r['method'] == method)
        lines.append(f"| {method.replace('_', ' ')} | {row['map_at_5']:.6f} |")
    lines += [f"| Personal frequency with 28-day decay (rejected) | {recency['primary_comparison']['recency_map_at_5']:.6f} |",
              f"| **Personal frequency + popularity pseudo-counts** | **{comparison['smoothed_map_at_5']:.6f}** |", '',
              '| Cohort | Users | Raw personal frequency | Smoothed personal frequency | Delta |',
              '|---|---:|---:|---:|---:|']
    rows = {(r['segment'], r['method']): r for r in smoothed['metrics']}
    for segment in ['all_target_users', 'five_target_users', 'template_target_users', 'cold_target_users',
                    'light_history_target_users', 'heavy_history_target_users', 'baseline_has_stale_recommendation']:
        old = rows[segment, 'personal_frequency']
        new = rows[segment, 'smoothed_personal_frequency']
        lines.append(f"| {segment.replace('_', ' ')} | {old['users']:,} | {old['map_at_5']:.6f} | {new['map_at_5']:.6f} | {new['map_at_5']-old['map_at_5']:+.6f} |")
    lines += ['', f"Paired user-bootstrap 95% interval for the primary MAP gain: **[{low:.6f}, {high:.6f}]**, 2,000 resamples, seed=42.",
        'This interval conditions on the same hold-out; it does not account for choosing experiments after examining it or for future temporal drift.', '',
        f"Users: {smoothed['user_outcomes']['improved']:,} improved, {smoothed['user_outcomes']['worsened']:,} worsened, {smoothed['user_outcomes']['unchanged']:,} have unchanged AP@5.",
        f"The smoothed lists gained {smoothed['target_items_added_to_lists']} target items and lost {smoothed['target_items_removed_from_lists']} (net +{smoothed['target_items_added_to_lists']-smoothed['target_items_removed_from_lists']}).",
        'Gained target types: '+', '.join(f'{key.replace("_", " ")}: {value}' for key, value in added_target_types.items())+'.',
        'Lost target types: '+', '.join(f'{key.replace("_", " ")}: {value}' for key, value in removed_target_types.items())+'.',
        'AP also changes when the same relevant items move within the list, so target-count gain and MAP gain are different quantities.', '',
        '## 6. Concrete examples and failure cases', '',
        'The original heavy/light viewers are retained. Two additional examples are deliberately selected by the largest gain/loss to explain behaviour; they are not representative samples.',
        'Titles/categories are representative original schedule values and remain untranslated source data.', '']
    for example in examples:
        lines += [f"### {example['label'].replace('_', ' ').title()}: `{example['user_id']}`", '',
                  example['selection'], '',
                  f"AP@5: {example['baseline_ap_at_5']:.6f} → {example['smoothed_ap_at_5']:.6f}.",
                  'Target IDs: '+' '.join(str(r['tv_show_id']) for r in example['targets'])+'.', '']
        for field, label in [('baseline_top5', 'Raw personal frequency'), ('smoothed_top5', 'Popularity-smoothed frequency')]:
            lines += [f'**{label}**', '', '| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |',
                      '|---:|---:|---|---|---:|---:|---:|---|']
            for rank, row in enumerate(example[field], 1):
                lines.append(f"| {rank} | {row['tv_show_id']} | {cell(row['title'])} | {cell(row['category'])} | {row['training_count']} | {row['smoothed_score']:.3f} | {row['validation_count']} | {'Yes' if row['validation_top5_hit'] else 'No'} |")
            lines.append('')
    lines += ['The original heavy viewer retains AP@5=0.76: strong repeated cartoon preferences survive the bounded bonus.',
        'The original light viewer is a useful counterexample to the average gain: inspect the table rather than assuming every sparse user improves. Popularity can push a genuinely relevant, less popular personal favourite down.',
        'The largest-loss example makes this failure explicit. A positive average gain does not remove individual regressions.', '',
        '## 7. Recommendation and limits', '',
        '**Use the popularity-smoothed personal-frequency score as the current offline choice.** It improves the measured MAP while retaining a simple explanation: personal repetition plus limited shared evidence.',
        'The implementation needs only training user-item counts and item viewer counts; no extra content or collaborative model is required for the selected score. The training timestamps were needed only for diagnosis and the rejected recency experiment.',
        'It remains popularity-biased, can hurt unusual preferences, and has no positive evidence for items with neither personal nor global training views. Only the labelled subset of TV airtime is observable.',
        'The known validation set was used for error analysis and to choose a second experiment after a failed first attempt. A later untouched temporal window would be needed for an independent quality estimate. No A/B, revenue or Kaggle result is claimed.', '',
        '## 8. Runtime and checks', '',
        f"Smoothed experiment: fit/input-event processing {smoothed['fit_seconds']:.3f} s, prediction {smoothed['predict_seconds']:.3f} s, end-to-end {smoothed['runtime_seconds']:.3f} s; peak RSS {smoothed['peak_rss_native_units']/1024**2:.1f} MiB on macOS.",
        'The two variants were rerun concurrently after a memory-only implementation adjustment; these wall-clock times are not controlled performance benchmarks.',
        f"Verification status: **{verification['status']}**. All {verification['training_airings_reconciled_with_original_counts']:,} training-airing events reconcile with the original counts.",
        'An independent standard-library verifier rebuilt all 4,914 rankings and 4,643 per-user AP values for each extension, checked all cohort metric rows, and confirmed that original prediction/target/metric artifact hashes are unchanged.',
        f"Extension unit tests: {tests['tests_run']} {tests['status']} (half-life weights, future-event rejection, pseudo-count arithmetic, strong-preference preservation and cold-start fallback).", '',
        '## 9. Reproduction and artifacts', '',
        'Run from the project root:', '', '```sh',
        '.venv/bin/python scripts/prepare_validation.py',
        '.venv/bin/python scripts/analyze_frequency_errors.py',
        '.venv/bin/python scripts/evaluate_recency.py',
        '.venv/bin/python scripts/evaluate_smoothing.py',
        '.venv/bin/python scripts/test_frequency_extensions.py',
        '.venv/bin/python scripts/verify_frequency_extensions.py',
        '.venv/bin/python scripts/render_frequency_report.py', '```', '',
        'These steps assume the original comparison artifacts exist; recreate them with `scripts/compare_methods.py` and `scripts/verify_results.py` first if necessary.',
        'Detailed artifacts: `personal_frequency_errors.json`, `personal_frequency_error_details.json`, `recency_*`, `smoothed_*`, `frequency_extension_tests.json` and `frequency_extension_verification.json`.',
        'Original data sources and package disclosures are unchanged; see README.md and the original validation report. This analysis and implementation were AI-assisted in the recorded session.', '']
    (OUT / 'frequency_improvement_report.md').write_text('\n'.join(lines))
    print(json.dumps(details, indent=2))
    print('Wrote reports/frequency_improvement_report.md')


if __name__ == '__main__':
    main()
