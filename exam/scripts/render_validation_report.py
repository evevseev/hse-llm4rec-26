# Generated with an AI assistant
"""Render the English report from measured experiment artifacts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
NAMES = {'popularity': 'Popularity', 'personal_frequency': 'Personal frequency',
         'cbf': 'Content-based filtering', 'association_rules': 'Association rules'}


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def main():
    results = json.loads((OUT / 'validation_results.json').read_text())
    prep = json.loads((OUT / 'validation_preparation.json').read_text())
    verified = json.loads((OUT / 'validation_verification.json').read_text())
    tests = json.loads((OUT / 'validation_unit_tests.json').read_text())
    examples = json.loads((OUT / 'validation_examples.json').read_text())
    metrics = {(r['segment'], r['method']): r for r in results['metrics']}
    population = results['population']
    statistics = prep['statistics']
    winner = results['winner_on_primary_map']
    base = metrics['all_target_users', 'popularity']['map_at_5']
    best = metrics['all_target_users', winner]['map_at_5']
    lines = [
        '# SWEET.TV temporal validation: four recommendation methods', '',
        'Experiment date: 2026-10-25. This is an offline hold-out experiment, not a Kaggle score or an online test.', '',
        '## Main result', '',
        f'**{NAMES[winner]} wins this hold-out with MAP@5 = {best:.6f}, versus {base:.6f} for popularity.**',
        f'The absolute gain is {best-base:.6f}; the relative gain over popularity is {(best/base-1)*100:.2f}%.',
        'The implemented CBF and association-rule configurations do not beat popularity on the primary metric.',
        'One fixed configuration per method was evaluated. There was no validation-based hyperparameter search.', '',
        '## 1. Time split and reconstructed interactions', '',
        '- Timezone assumption: **Europe/Kyiv**. Convert log and schedule starts to Unix seconds.',
        '- Training: **2020-03-09 00:00:00 to 2020-05-18 00:00:00**, ISO weeks 11–20.',
        '- Validation: **2020-05-18 00:00:00 to 2020-07-27 00:00:00**, ISO weeks 21–30.',
        '- Schedule end = timezone-aware start + supplied duration in elapsed seconds.',
        '- Match equal channel IDs with positive overlap of half-open intervals.',
        '- Merge all viewing fragments per user and airing by interval union, so duplicate/overlapping logs do not double-count seconds.',
        '- A watched airing has merged overlap / full airing duration **>= 0.8**. Count qualified airings per user and programme ID.',
        '- Exclude zero IDs and nonpositive durations. Exclude entire airings crossing the start, split or end boundary; do not shorten the denominator.',
        '- A log spanning a boundary can contribute only its overlap with eligible airings inside the corresponding window.', '',
        f"There are {statistics['train_qualified_user_airings']:,} qualified training user-airings and {statistics['validation_qualified_user_airings']:,} validation user-airings.",
        f"Fragment merging adds {statistics['train_qualified_only_after_fragment_merging']:,} and {statistics['validation_qualified_only_after_fragment_merging']:,} qualified user-airings respectively that no individual fragment would qualify.",
        f"The timezone-aware elapsed duration matches `duraton` in every log row; mismatches: {statistics['reported_duration_mismatches_after_timezone']}.",
        f"The boundary rule excludes {statistics['boundary_crossing_labelled_airings_excluded']:,} labelled airings; this includes airings crossing the overall observation boundaries.", '',
        'This is a reproducible reconstruction of Kaggle labels, not access to the hidden label-building code. Fragment-merging and tie rules are our explicit choices.', '',
        '## 2. Candidates, repetitions and leakage control', '',
        f"The common candidate pool has **{population['candidate_items']:,}** nonzero IDs with a positive-duration airing overlapping validation.",
        'It is timestamp-based across both schedule files, including boundary carry-over; it is not just the set of IDs in the second file.',
        'Previously watched items remain eligible for every method. There is no seen-item exclusion.',
        'All interaction statistics, content vocabulary/IDF, user profiles and association rules use training only.',
        'CBF uses descriptions only from airings starting inside the training window. Validation descriptions are used solely to display example titles/categories, never to score items.',
        'The all-user list only supplies row IDs; zero rows for users without training views contribute no behavioural statistics.',
        'Validation viewing counts are loaded by the comparison script only after every model and prediction is fixed.',
        'The weeks 31–42 schedule is not read by this experiment.', '',
        f"There are {population['candidate_items_without_training_metadata']:,} candidates without training metadata and {population['candidate_items_without_training_views']:,} without qualified training views.",
        'CBF assigns no positive similarity to candidates without a training feature vector. Rules cannot produce evidence for items with no training viewers.', '',
        '## 3. Quality calculation', '',
        'For each user, choose up to five validation programmes by decreasing qualified-airing frequency; ties use ascending programme ID.',
        'These IDs form the relevant set. A predicted item watched outside this top five is not a metric hit.', '',
        '`AP@5 = sum(P@rank * relevant_at_rank, rank=1..5) / min(5, number_of_targets)`.',
        '`MAP@5 = mean(AP@5 over users with at least one target)`.', '',
        'Target order determines top-five membership when constructing the label, but standard AP uses relevance membership and prediction ranks, not exact target-rank matching.',
        f"The main population is **{population['evaluated_users']:,}** users. **{population['users_without_validation_targets_excluded']:,}** of {population['all_log_users']:,} log users have no qualified validation target and are excluded, not silently assigned zero AP.",
        f"Of {population['template_users']:,} template users, {population['template_users_without_targets']} have no local validation target.",
        'All users still receive predictions, including users excluded from MAP.',
        'Target-size distribution: '+', '.join(f'{size} targets: {count} users' for size, count in sorted(population['target_size_distribution'].items()))+'.', '',
        'Precision@5 uses five predicted slots; recall@5 divides hits by the target-set size; hit rate@5 measures at least one hit.',
        'The ten-week validation horizon is shorter than the twelve-week final horizon. This is a single historical hold-out, not a final generalization guarantee.', '',
        '## 4. Implemented methods and exact Top-5 construction', '',
        '### Popularity', '',
        'Score = number of distinct training users with a qualified view of the item. Rank candidates by decreasing score, then increasing ID.',
        'Using unique users prevents a single heavy viewer from dominating the global baseline.', '',
        '### Personal frequency', '',
        'Score = the user\'s number of qualified training airings for the programme. Rank positive scores by count, global popularity, then ID.',
        'This directly tests continuation of observed viewing habits. No decay, recency tuning or smoothing is applied.', '',
        '### Content-based filtering', '',
        '- Union metadata values per training item. Category weight=2; each distinct genre weight=2; director and actor tokens weight=1; release-decade token weight=0.3.',
        '- Split person fields on commas, semicolons or vertical bars; normalize case and whitespace. Use the first parsed release year to obtain a decade.',
        '- Fit a DictVectorizer and smoothed TF-IDF on the training item catalogue only. TF-IDF IDF is `log((1+n_items)/(1+document_frequency))+1`.',
        '- L2-normalize item vectors. Form each user profile as the sum of watched-item vectors weighted by `log1p(qualified_airing_count)`, then L2-normalize it.',
        '- Score by cosine similarity. Titles and programme identity are not content features. Missing attributes simply omit tokens.',
        f"- The fitted content space has {results['model_sizes']['content_features']:,} features.", '',
        '### Association rules', '',
        '- One binary basket per training user: items with at least one qualified airing. Count users, not repeated airings, for support.',
        '- For each directed pair A -> B, confidence = users(A and B) / users(A). Remove self-rules.',
        '- Require at least 3 supporting users and confidence >=0.02. Shrink confidence by `support/(support+10)`.',
        '- Keep at most 100 consequents per antecedent by shrunk confidence, breaking ties by item ID.',
        '- Candidate score = sum over the user\'s watched antecedents of `log1p(personal_count) * shrunk_confidence`.',
        f"- There are {results['model_sizes']['retained_rules']:,} retained directed rules. This is an association model, not sequential next-program prediction.", '',
        '### Shared list policy', '',
        'Rank strictly positive method scores, break score ties by training popularity then item ID, take up to five, and fill missing positions from the popularity list while skipping duplicate IDs.',
        'A user with no qualified training interaction receives the same popularity top five under every method. Scores across methods are not calibrated probabilities and are not fused.', '',
        '## 5. Results', '',
        '### Primary population', '',
        '| Method | MAP@5 | Precision@5 | Recall@5 | Hit rate@5 |',
        '|---|---:|---:|---:|---:|']
    for method in NAMES:
        row = metrics['all_target_users', method]
        lines.append(f"| {NAMES[method]} | {row['map_at_5']:.6f} | {row['precision_at_5']:.6f} | {row['recall_at_5']:.6f} | {row['hit_rate_at_5']:.6f} |")
    lines += ['', '### MAP@5 by cohort', '',
              '| Cohort | Users | Popularity | Personal frequency | CBF | Association rules |',
              '|---|---:|---:|---:|---:|---:|']
    for segment, label in [('five_target_users', 'Five targets'), ('template_target_users', 'Template with targets'),
                           ('warm_target_users', 'Nonempty training history'), ('cold_target_users', 'Empty training history'),
                           ('light_history_target_users', '1–10 training airings'), ('heavy_history_target_users', 'At least 100 training airings')]:
        n = metrics[segment, 'popularity']['users']
        lines.append(f'| {label} | {n:,} | '+' | '.join(f"{metrics[segment, m]['map_at_5']:.6f}" for m in NAMES)+' |')
    lines += ['', 'Cohort boundaries 1–10 and >=100 are descriptive, not tuned switching thresholds. No switching hybrid was evaluated.', '',
              '### Paired user bootstrap', '',
              '2,000 paired bootstrap resamples, seed=42. Intervals are conditional on this hold-out, not temporal uncertainty estimates or online-effect evidence.', '',
              '| Difference in MAP@5 | Mean | 95% interval |', '|---|---:|---|']
    for comparison, values in results['paired_comparisons'].items():
        low, high = values['paired_bootstrap_95_percent_interval']
        lines.append(f"| {comparison.replace('_', ' ')} | {values['mean_delta']:.6f} | [{low:.6f}, {high:.6f}] |")
    lines += ['', '### Recommendation diagnostics', '',
              '| Method | Distinct recommended items | Mean fallback slots | Fraction previously watched in training |',
              '|---|---:|---:|---:|']
    for method, row in results['recommendation_diagnostics'].items():
        lines.append(f"| {NAMES[method]} | {row['catalogue_items_recommended']} | {row['mean_fallback_slots']:.3f} | {row['fraction_recommendations_seen_in_training']:.2%} |")
    lines += ['', 'Counts concern the main evaluated population. A popularity baseline is its own method, so its fallback-slot count is recorded as zero.', '',
              '## 6. Two fixed user examples', '',
              'Choose the maximum and minimum positive training-airing counts among template users with nonempty validation targets; user ID breaks ties.',
              'Validation-target availability restricts the illustration cohort, but method performance is never used to select examples. The same users appear under all methods.',
              'Titles/categories are representative original schedule values; some titles vary across airings of the same ID. They remain untranslated source data.',
              '`Target hit` means membership in the validation top five. The validation count can be positive even for a target miss.', '']
    for example in examples:
        lines += [f"### {example['label'].title()} viewer: `{example['user_id']}`", '',
                  f"Training qualified airings: {example['training_qualified_airings']}; distinct programmes: {example['training_distinct_items']}.", '',
                  'Validation targets:', '', '| ID | Original title | Category | Qualified validation airings |', '|---:|---|---|---:|']
        for row in example['validation_targets']:
            lines.append(f"| {row['tv_show_id']} | {cell(row['title'])} | {cell(row['category'])} | {row['count']} |")
        for method in NAMES:
            details = example['methods'][method]
            lines += ['', f"**{NAMES[method]} — AP@5={details['ap_at_5']:.6f}**", '',
                      '| Rank | ID | Original title | Category | Training count | Validation count | Target hit |',
                      '|---:|---:|---|---|---:|---:|---|']
            for row in details['recommendations']:
                lines.append(f"| {row['rank']} | {row['tv_show_id']} | {cell(row['title'])} | {cell(row['category'])} | {row['qualified_training_airings']} | {row['qualified_validation_airings']} | {'Yes' if row['in_validation_top5'] else 'No'} |")
        lines.append('')
    lines += ['## 7. Interpretation and current strategy', '',
        f"Of {population['validation_top5_items_total']:,} user-target pairs, {population['validation_top5_items_seen_in_own_training']:,} ({population['validation_top5_items_seen_in_own_training']/population['validation_top5_items_total']:.2%}) already appear in that user\'s qualified training history.",
        'This supports testing continuation of habits; it does not imply that every user is stable or that unseen programmes are irrelevant.', '',
        '**Heavy viewer:** personal frequency retains the strongly repeated children\'s programmes and hits four targets, AP@5=0.76. Popularity and association rules mainly recommend news and achieve 0.20.',
        'The CBF profile uses log counts and attribute similarity rather than programme identity; for this mixed-history viewer it ranks news above the dominant repeated cartoon and reaches only 0.066667.',
        'This example illustrates a failure of the implemented content representation, not proof that all content models fail.', '',
        '**Light viewer:** the single training programme is 200337. Personal frequency keeps it and fills from popularity, reaching AP@5=0.60.',
        'CBF proposes the related morning show 20088, not observed in this user\'s training history but watched twice in validation; it is a supported example of relevant new-to-observed-history content.',
        'Some other unfamiliar CBF suggestions, such as 200477 and 5900275, have no qualified validation views, so novelty alone is not evidence of useful discovery.',
        'Association rules link the morning programme to widely co-viewed news and another morning programme, giving AP@5=0.52, versus 0.40 for popularity.', '',
        'Association rules use co-viewing links absent from pure CBF, but confidence tends to favour common consequents.',
        'The measured rules model recommends only 16 distinct items across the evaluated population, close to popularity-driven behaviour; it slightly improves hit rate yet loses MAP because placement matters.',
        'CBF covers more items and can score training-described items with no views, but its coarse/missing attributes and lack of identity persistence are insufficient in this configuration.', '',
        '**Current choice:** personal frequency with the shared popularity fallback is the strongest implemented strategy on this hold-out, particularly for heavy histories.',
        'For the 1–10-airing cohort it is slightly below popularity, so a history-dependent switch or a hybrid is a reasonable future experiment, not an already measured improvement.',
        'The two required non-baseline algorithms, CBF and association rules, are each independently implemented and evaluated even though the simple baseline wins.', '',
        '## 8. Limitations', '',
        '- Only about 10.8% of rows in the first schedule carry an ID; all conclusions concern this labelled subset, not all TV consumption.',
        '- An 80% rule rejects partial viewing; valid fragments must be combined. Long unattended sessions may still qualify and do not reveal enjoyment.',
        '- Removing boundary-crossing airings is conservative but discards observations. The hidden Kaggle pipeline may make different choices.',
        '- CBF deliberately excludes future metadata to respect the strict schedule-use constraint; many validation candidates consequently have no vector.',
        '- Counts reward repeated programmes and frequent airings. A watch is not a rating, causal preference estimate, or satisfaction measure.',
        '- Absence from this platform log is not proof that a user has never seen a programme elsewhere.',
        '- The target top-five cutoff penalizes other programmes the user actually watched; examples explicitly show both kinds of evidence.',
        '- One ten-week hold-out cannot establish twelve-week performance or performance after changes in schedules and user populations.',
        '- No validation hyperparameters were fitted. Selecting a winning method on this hold-out still uses it for model selection; a later temporal test is needed for an independent estimate.',
        '- No Kaggle score, live A/B test, revenue uplift or online effect is claimed.', '',
        '## 9. Runtime, environment and verification', '',
        f"Preprocessing: {prep['runtime_seconds']:.3f} seconds; peak RSS {prep['peak_rss_native_units']/1024**2:.1f} MiB on macOS.",
        f"Comparison including evaluation/artifact output: {results['runtime_seconds']:.3f} seconds; peak RSS {results['peak_rss_native_units']/1024**2:.1f} MiB.", '',
        '| Stage | Seconds |', '|---|---:|']
    for label, duration in results['timings'].items():
        lines.append(f'| {label} | {duration:.6f} |')
    lines += ['', 'Model timings share the separately reported input/matrix construction stage. These are one-run wall-clock measurements, not repeated benchmarks.',
        'The personal-frequency implementation currently scans all candidates in Python; its measured runtime should not be interpreted as inherent algorithmic inferiority to vectorized CBF.', '',
        f"Environment: {results['environment']['platform']}; Python {results['environment']['python'].split()[0]}; NumPy {results['environment']['numpy']}; SciPy {results['environment']['scipy']}; scikit-learn {results['environment']['scikit_learn']}.",
        'Model predictions are deterministic; seed=42 is used for bootstrap and verification sampling only.', '',
        f"Independent artifact verification status: **{verified['status']}**. It checked {verified['prediction_rows_checked']:,} predictions, rebuilt {verified['target_users_checked']:,} targets, independently recomputed {verified['metric_rows_independently_recomputed']} MAP rows and recomputed {verified['association_rules_independently_recomputed']} sampled rules from training baskets.",
        f"Unit-test status: **{tests['status']}**, {tests['tests_run']} tests for AP semantics, empty targets, deduplicated interval unions, fragment aggregation, DST elapsed time and ranking/fallback. Details: `validation_unit_tests.json`.", '',
        '## 10. Reproduction and disclosures', '',
        'See `../README.md` for commands. The full configuration, input hashes, metrics, per-user predictions, targets, retained rules and verification hashes are saved alongside this report.',
        'External packages: NumPy, SciPy and scikit-learn for sparse algebra, TF-IDF and normalization; Python zoneinfo for the system timezone database.',
        'No pretrained model or third-party recommender implementation is used. Recommendations and AP calculations are implemented in this project.',
        'AI-assisted code and analysis are part of this session; retain the corresponding session export for the exam records.', '']
    (OUT / 'validation_report.md').write_text('\n'.join(lines))
    print('Wrote reports/validation_report.md')


if __name__ == '__main__':
    main()
