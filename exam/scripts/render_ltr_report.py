# Generated with an AI assistant
"""Render the English history/schedule learning-to-rank experiment report."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
NAMES = {'history_schedule_ranker': 'History + schedule pairwise ranker',
         'smoothed_personal_frequency': 'Personal frequency + popularity', 'popularity': 'Popularity'}


def load(name):
    return json.loads((OUT / name).read_text())


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def main():
    plan, training, result = load('ltr_plan.json'), load('ltr_training_results.json'), load('ltr_results.json')
    verification, tests = load('ltr_verification.json'), load('ltr_feature_tests.json')
    importance, examples = load('ltr_feature_importance.json'), load('ltr_examples.json')
    rows = {(r['segment'], r['method']): r for r in result['metrics']}
    model_map = rows['all_target_users', 'history_schedule_ranker']['map_at_5']
    ref_map = rows['all_target_users', 'smoothed_personal_frequency']['map_at_5']
    low, high = result['comparison_vs_reference']['paired_bootstrap_95_percent_interval']
    injected = sum(r['injected_positives'] for r in training['windows'])
    lines = [
        '# SWEET.TV: learned ranking with history and schedule features', '',
        'Experiment date: 2026-10-25. One fixed model was trained with supervision ending no later than week 20. Weeks 21–30 were used only for evaluation within this experiment.', '',
        '## Main result', '',
        f"The history/schedule ranker achieved **MAP@5={model_map:.6f}**, versus **{ref_map:.6f}** for the existing personal-frequency + popularity rule.",
        f"The paired difference is {model_map-ref_map:+.6f}; its conditional 95% bootstrap interval is **[{low:.6f}, {high:.6f}]**, including zero.",
        'There is no demonstrated overall gain in this run. The model improves the previously defined heavy-viewer cohort but loses on light histories. No settings were changed after observing outer quality.', '',
        '## 1. Supervised examples entirely inside the earlier period', '',
        'A query is one user at one historical prediction cutoff. Features use only qualified airings ending before that cutoff. Labels identify up to five most frequently watched programmes in the next two weeks.', '',
        '| Query window | Feature history | Label period | Queries | Positive labels | Positives appended during training |',
        '|---|---|---|---:|---:|---:|']
    history_names = ['Weeks 11–14', 'Weeks 11–16', 'Weeks 11–18']
    label_names = ['Weeks 15–16, April 6–20', 'Weeks 17–18, April 20–May 4', 'Weeks 19–20, May 4–18']
    for history_name, label_name, window in zip(history_names, label_names, training['windows']):
        lines.append(f"| {window['name']} | {history_name} | {label_name} | {window['queries']:,} | {window['positive_rows']:,} | {window['injected_positives']:,} |")
    lines += ['',
        f"Total: **{training['training_queries']:,} queries**, **{training['training_rows']:,} user-item rows**, **{training['positive_rows']:,} positive rows**, **{training['features']} features**.",
        'The final label boundary is May 18, exactly when outer validation starts. There are no supervised labels from weeks 21–30 in model fitting.',
        'All three earlier windows are used for training. There is no internal model search or early stopping; the configuration is fixed before fitting.',
        'Labels are binary relevance to the future top five, not binary membership in the training history. A negative label is not evidence of dislike or lack of enjoyment.', '',
        'History follows the established construction: channel/interval join, per-user/airing interval union, >=80% coverage, nonzero programme IDs and exclusion of boundary-crossing airings.',
        'The richer event export adds the actual channel, airing start/end and merged viewed seconds. All 316,311 training user-airings reconcile with the frozen original training counts.', '',
        '## 2. Candidate generation and exactly five recommendations', '',
        'Each user receives 100 natural candidates from labelled programmes available in the prediction schedule:',
        '1. Top 50 by the existing `personal_count + 3 * training_viewers/max_viewers` score.',
        '2. Top 30 by schedule-channel compatibility multiplied by `log1p(future_airings_per_week)`.',
        '3. Top 20 by scheduled airings per week.',
        '4. Deduplicate and fill to 100 by the baseline ordering.',
        'Schedule-channel compatibility is the dot product of the programme\'s future airing-channel distribution and the user\'s historical channel share, weighted by qualified viewed seconds.', '',
        f"During training only, missing positive items are appended to their query ({injected:,} total); each query then has 100–105 items. This is supervised candidate sampling, and the injection flag is never a feature.",
        'Outer prediction never appends positives: candidate selection does not read target behaviour. Every original baseline Top-5 is present in its candidate set, so candidate generation does not remove the reference solution.',
        'For warm users, rank the candidates by the learned margin, tie-break by training popularity and item ID, and output the first five. Negative margins are valid ranking scores; sigmoid-transformed margins are equivalent positive monotone scores, not calibrated viewing probabilities.',
        'Users without qualified history receive exactly the same training-popularity Top-5 as all previous methods. Previously watched programmes remain eligible.', '',
        '## 3. History and schedule features', '',
        '| Feature group | Examples and source |', '|---|---|',
        '| Personal repetition | Qualified count, log-count, personal share, weekly rate, personal rank. History before the query cutoff only. |',
        '| Recency | Counts in the last and preceding 14 elapsed days, recent trend, days since last qualified item airing. |',
        '| Global evidence | Distinct historical viewers, historical qualified-airing count, weekly rate, viewer fraction. |',
        '| Existing rule | Baseline score and reciprocal baseline rank, computed from the current query history. |',
        '| User context | History volume, distinct items, history calendar days, favorite share, channel concentration. |',
        '| Future availability | Airings per week, fraction of distinct airing-start days, channels, first/last relative position and mean duration. |',
        '| Schedule compatibility | Historical channel share and weekday/four-hour airing-start-slot share matched against the future schedule. |', '',
        'Only `tv_show_id`, channel, start and duration are read from future schedule rows. Titles, genres, categories, actors and future viewers are not used to score items. Source titles/categories are looked up only for human-readable examples.',
        'Channel and start-time preferences are based on qualified historical viewed seconds, not future activity. The time-slot feature uses the airing start bucket, not a claim to reconstruct every minute of the user\'s daily viewing.',
        'Calendar-rate and position normalizations reduce differences between two-week training-label windows and ten-week outer availability. They do not eliminate the horizon mismatch.',
        'There are no explicit user/programme ID columns in the feature matrix. IDs identify queries/candidates and break deterministic ties.', '',
        '## 4. Fixed learning-to-rank implementation', '',
        'The ranker uses XGBoost `rank:pairwise`: it learns comparisons between relevant and non-relevant items inside the same user/time query.',
        'It is trained on future top-five membership from earlier windows, rather than asking every historically observed item to have the same positive factorization target.', '',
        '| Parameter | Value |', '|---|---|']
    for key, value in plan['parameters'].items():
        lines.append(f'| {key} | {value} |')
    lines += ['',
        'The pairwise objective is a surrogate, not direct maximization of MAP@5. Declaring `map@5` does not mean outer labels are passed to fitting: no eval_set or early stopping is used.',
        'The trained model is saved before outer feature construction. Outer predictions and feature hashes are frozen before the evaluation script opens held-out viewing counts.',
        'The outer period had already been inspected in previous project experiments, and the existing bonus-3 baseline was selected there. Within this new ranker experiment it is evaluation-only; the result is not described as a newly untouched independent test.', '',
        '## 5. Outer results on weeks 21–30', '',
        'The target pool, original 4,643 nonempty-target users and AP@5 denominator are unchanged. Predictions are also produced for all 4,914 log users. Cold-user fallback and repeat policy are unchanged.', '',
        '| Method | MAP@5 | Precision@5 | Recall@5 | Hit rate@5 |', '|---|---:|---:|---:|---:|']
    for method in NAMES:
        row = rows['all_target_users', method]
        lines.append(f"| {NAMES[method]} | {row['map_at_5']:.6f} | {row['precision_at_5']:.6f} | {row['recall_at_5']:.6f} | {row['hit_rate_at_5']:.6f} |")
    lines += ['', '| Cohort | Users | Ranker MAP@5 | Current rule MAP@5 |', '|---|---:|---:|---:|']
    for segment in ['five_target_users', 'template_target_users', 'warm_target_users', 'cold_target_users', 'light_history_target_users', 'heavy_history_target_users']:
        lr = rows[segment, 'history_schedule_ranker']; base = rows[segment, 'smoothed_personal_frequency']
        lines.append(f"| {segment.replace('_', ' ')} | {lr['users']:,} | {lr['map_at_5']:.6f} | {base['map_at_5']:.6f} |")
    lines += ['',
        f"Per-user AP changes: {result['user_outcomes']['improved']} improved, {result['user_outcomes']['worsened']} worsened, {result['user_outcomes']['unchanged']} unchanged.",
        f"The mean difference is {result['comparison_vs_reference']['mean_delta']:+.6f}; 2,000 paired user bootstrap resamples, seed 42, give [{low:.6f}, {high:.6f}]. This conditional interval includes zero and does not establish an overall gain or a clear overall loss.",
        'The heavy-history result is descriptive on the previously defined >=100-view cohort; it was not used to fit a new switching threshold or alter the model after evaluation.', '',
        '## 6. Candidate quality versus ranking quality', '',
        f"Mean target recall in the 100 natural candidates is **{result['candidate_mean_target_recall']:.2%}**. This averages the fraction of each user\'s target set retrieved, not the fraction of all schedule programmes.",
        f"A diagnostic oracle that places all retrieved targets first, while retaining the mandatory cold-user fallback, would have MAP@5 **{result['oracle_map_at_5_with_fixed_cold_fallback']:.6f}**.",
        'The oracle uses held-out labels for diagnosis only and is not an implemented recommender or claimed performance. The measured gap shows that ranking errors remain important alongside missing candidates.',
        'The reference Top-5 is present for every user, and therefore the reranking comparison does not benefit from excluding baseline recommendations.', '',
        '| Method | Catalogue items recommended | Hits absent from own training | Hits for items with no training viewers |',
        '|---|---:|---:|---:|']
    for method, d in result['diagnostics'].items():
        lines.append(f"| {NAMES[method]} | {d['catalogue_items_recommended']} | {d['target_hits_absent_from_own_training']} | {d['target_hits_without_any_training_viewer']} |")
    lines += ['',
        'The ranker records 28 user-item target hits for items with no training viewers, whereas the reference records none. Schedule/context features allow such items to be scored without a pre-existing item factor.',
        'This does not establish a causal incremental benefit of schedule features: no feature ablation was selected or evaluated on the outer period.', '',
        '## 7. What the fitted model uses', '',
        'Top training split-gain importances:', '', '| Feature | Normalized gain |', '|---|---:|']
    for row in importance[:12]:
        lines.append(f"| {row['feature']} | {row['normalized_gain']:.2%} |")
    lines += ['',
        'Baseline rank/score and user-history volume dominate, while future airing rate and channel compatibility also appear near the top. These are training gain importances, not causal effects, user satisfaction measures or standalone validation improvements.', '',
        '## 8. Previously fixed user examples', '',
        'The same heavy/light viewers are retained; original-language titles/categories remain source data. Both examples happen to have unchanged AP relative to the reference, so they are not presented as representative improvements.', '']
    for example in examples:
        lines += [f"### {example['label'].title()} viewer `{example['user_id']}`", '',
            'Target IDs: '+' '.join(map(str, example['target_ids']))+'.',
            'Target IDs retrieved naturally: '+' '.join(map(str, example['target_ids_in_candidates']))+'.', '']
        for method in NAMES:
            detail = example['methods'][method]
            lines += [f"**{NAMES[method]} — AP@5={detail['ap_at_5']:.6f}**", '',
                '| Rank | ID | Original title | Category | Training count | Validation count | Target hit |',
                '|---:|---:|---|---|---:|---:|---|']
            for row in detail['recommendations']:
                lines.append(f"| {row['rank']} | {row['tv_show_id']} | {cell(row['title'])} | {cell(row['category'])} | {row['training_count']} | {row['validation_count']} | {'Yes' if row['target_hit'] else 'No'} |")
            lines.append('')
    lines += ['## 9. Verification and limitations', '',
        f"Feature tests: **{tests['status']}**, {tests['tests_run']} tests, including invariance to appended future viewing behaviour, boundary handling, time normalization and training-only positive injection.",
        f"Artifact verification: **{verification['status']}**. It reconciled {verification['qualified_history_airings_reconciled']:,} qualified historical airings, rebuilt all {verification['training_positive_labels_rebuilt']:,} training labels and regenerated {verification['training_feature_rows_regenerated']:,} training feature rows from cutoff-bound snapshots.",
        f"It also regenerated {verification['outer_feature_rows_regenerated_without_labels']:,} outer feature rows without labels, replayed all model margins and rebuilt all {verification['all_ranker_top5_lists_rebuilt']:,} Top-5 lists, then independently recomputed {verification['cohort_metric_rows_recomputed']} cohort-metric rows.",
        'Snapshot regeneration is a reproducibility check using the feature module; separate direct checks compare personal counts/global viewer features to raw historical counts. It is not claimed to be an independent reimplementation of every feature formula.',
        'Frozen original target/reference hashes match. Training-label ends are all <=May 18 and no positive injection occurs at outer prediction.',
        'A first evaluation attempt failed only when serializing a NumPy integer to JSON. The export fix was retried with identical model and prediction hashes; one unique model configuration was evaluated and no parameter/feature selection used the held-out result.', '',
        'Limitations:',
        '- Training labels cover two-week futures after 4/6/8 weeks of history; outer prediction covers ten future weeks after ten training weeks. Rate normalization does not remove this distribution shift.',
        '- Positive injection makes training candidate sets more complete than natural inference candidates; its sampling bias and the 100-candidate retrieval ceiling remain.',
        '- Only the labelled subset of schedule airtime is observable. >=80% qualified watches do not establish enjoyment or satisfaction.',
        '- This is one fixed ranking model and one known outer period. No post-evaluation tuning or history-dependent hybrid was performed.',
        '- Earlier project decisions used the outer hold-out, so the broader project is not an untouched-test study even though this model\'s supervised labels/features respect time.',
        '- No Kaggle score, live A/B, revenue or online-effect claim is made.', '',
        '## 10. Current strategy and reproduction', '',
        '**Retain the existing personal-frequency + popularity rule as the current global choice.** The learned model nearly matches it and shows useful schedule-aware capability, but has no demonstrated overall MAP improvement in this evaluation.',
        'The requested learned-ranking implementation, model, features and comparisons are saved and reproducible; no additional model was tried against the outer labels.', '',
        f"Training: {training['fit_seconds']:.3f} s model fit, {training['runtime_seconds']:.3f} s including feature/dataset generation; peak RSS {training['peak_rss_native_units']/1024**2:.1f} MiB on macOS.",
        f"Successful prediction/evaluation attempt: {result['prediction_and_feature_seconds']:.3f} s feature/prediction/export stage, {result['runtime_seconds']:.3f} s end-to-end; peak RSS {result['peak_rss_native_units']/1024**2:.1f} MiB. Dataset extraction and package installation are excluded.",
        f"Environment: Python {training['environment']['python'].split()[0]}, {training['environment']['platform']}, XGBoost {training['environment']['xgboost']}, NumPy {training['environment']['numpy']}. Seed=42; ranker n_jobs=4; BLAS thread pools controlled separately.", '',
        'After the original processed/reference artifacts exist:', '', '```sh',
        '.venv/bin/python -m pip install -r requirements.txt',
        '.venv/bin/python scripts/setup_xgboost_openmp.py',
        '.venv/bin/python scripts/prepare_ltr_history.py',
        '.venv/bin/python scripts/test_ltr_features.py',
        '.venv/bin/python scripts/train_ltr.py',
        '.venv/bin/python scripts/evaluate_ltr.py',
        '.venv/bin/python scripts/verify_ltr.py',
        '.venv/bin/python scripts/render_ltr_report.py', '```', '',
        'On Apple Silicon macOS this workspace uses a project-local conda-forge llvm-openmp 15.0.5 runtime, stored under ignored `.venv/libomp/`; no system OpenMP installation was changed. Its source URL and archive hash are recorded in `.venv/libomp_source.json`.',
        'Artifacts: `ltr_plan.json`, `ltr_training_queries.csv`, `ltr_training_results.json`, `ltr_feature_importance.json`, `ltr_prediction_manifest.json`, `ltr_predictions.csv`, `ltr_per_user_metrics.csv`, `ltr_metrics.csv`, `ltr_results.json`, `ltr_examples.json`, `ltr_feature_tests.json`, and `ltr_verification.json`.',
        'The saved model is `data/processed/learning_to_rank/ranker.ubj`; training/evaluation feature caches and qualified channel/time history are in the same data directory.',
        '**External implementation disclosure:** XGBoost provides the pairwise boosted-tree ranking algorithm. Feature engineering, temporal sample construction, candidate generation and evaluation are project code. NumPy/SciPy and threadpoolctl provide numeric/runtime support. No pretrained model was used. Work was AI-assisted in this recorded session.', '']
    (OUT / 'ltr_report.md').write_text('\n'.join(lines))
    print('Wrote reports/ltr_report.md')


if __name__ == '__main__':
    main()
