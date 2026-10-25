# Generated with an AI assistant
"""Render the English analysis of exactly three repeat-aware variants."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
NAMES = {'smoothed_personal_frequency': 'Personal frequency + popularity',
         'personalized_pagerank': 'Original PPR (log-count seeds)',
         'implicit_als': 'Original implicit ALS (binary targets)',
         'ppr_raw_counts': 'PPR with raw-count seeds',
         'als_log_counts_weighted': 'Log-count MF, weighted confidence',
         'als_log_counts_uniform': 'Log-count MF, uniform confidence'}


def load(name):
    return json.loads((OUT / name).read_text())


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def main():
    result = load('repeat_aware_results.json')
    verification, tests = load('repeat_aware_verification.json'), load('repeat_aware_unit_tests.json')
    examples = load('repeat_aware_examples.json')
    metrics = {(r['segment'], r['method']): r for r in result['metrics']}
    base = metrics['all_target_users', 'smoothed_personal_frequency']['map_at_5']
    variants = list(result['variants'])
    diagnostics = result['repeat_diagnostics']
    repeated_total = diagnostics['implicit_als']['repeated_targets_training_count_ge_10']
    strong_n = diagnostics['implicit_als']['strong_favorite_users']
    relevant_strong_n = diagnostics['implicit_als']['strong_favorite_also_validation_target_users']
    lines = [
        '# Repeat-aware PageRank and matrix-factorization variants', '',
        'Experiment date: 2026-10-25. These are local hold-out results, not Kaggle or online results.', '',
        '## Main result', '',
        '**Explicitly modelling repeat strength substantially repairs the collaborative models, especially ALS. None of these three variants beats the current personal-frequency + popularity score overall.**', '',
        '| Method | Primary MAP@5 | Delta vs current best |', '|---|---:|---:|']
    for method in NAMES:
        value = metrics['all_target_users', method]['map_at_5']
        lines.append(f'| {NAMES[method]} | {value:.6f} | {value-base:+.6f} |')
    lines += ['', 'Exactly three variants were specified before running this batch. No further damping, factor-count, regularization or confidence sweep was performed.',
        'The variants were motivated by earlier errors on this same known hold-out; this is model-selection evidence, not an untouched test estimate.', '',
        '## 1. Why the original models weakened favorites', '',
        '### PPR compresses frequency and then diffuses it', '',
        f"For the fixed heavy viewer, programme 12001682 had 401 training watches and news programme 2400480 had 62. Their raw frequency ratio is {401/62:.2f}, but their log1p seed-weight ratio is only {math.log1p(401)/math.log1p(62):.2f}.",
        'The original graph model therefore gives a much weaker relative advantage to the favorite before diffusion even starts. With damping 0.85, only the restart component directly anchors the ranking to these seeds; co-view paths also reshape the scores.',
        'The graph itself counts binary common viewers, so it does not distinguish one from many watches by a particular user when building item links.', '',
        '**Important qualification:** not every strong favorite was lost. Under the training-only dominant-favorite definition below, original PPR already retained all 203 favorites in Top-5. Its weakness also concerns secondary repeated programmes, ordering and mixed histories.', '',
        '### Binary-target ALS does not predict viewing frequency', '',
        'The original model uses `p=1` for any observed pair and changes confidence with `1+20*log1p(count)`. One and 401 watches both ask the dot product to approach one.',
        'Confidence changes the cost of an error, not the target level. A lower-frequency or previously unobserved programme can obtain a higher dot product than a repeated favorite.',
        'This is appropriate for one kind of implicit-preference task but not necessarily for selecting future most-frequent programmes.',
        'The previous independent objective and normal-equation checks passed, so this batch changes the modelling assumptions rather than treating poor MAP as proof of a solver bug.', '',
        '## 2. Frozen protocol', '',
        '- Train on weeks 11–20; validate on weeks 21–30. Same Europe/Kyiv timestamp handling and boundary rules.',
        '- Same merged per-user/airing intervals, >=80% watch threshold, qualified-airing counts and exclusion of ID zero.',
        '- Same validation target construction, 6,384 candidates and 4,643 nonempty-target users for primary MAP@5.',
        '- Same allowance for already-watched programmes; same positive-score ordering, popularity/ID tie-breaks and popularity fallback.',
        '- Same cold-user output. No validation behaviour enters training or features.',
        '- Original reference predictions are reused unchanged. The input, target, reference and graph hashes are verified.',
        '- Original 32 factors, 15 iterations, regularization 0.1, initialization and seed 42 remain fixed for both new MF variants.', '',
        '## 3. Three simple changes', '',
        '### A. Raw-frequency personalization for PPR', '',
        '`seed(u,i) = count(u,i) / sum_j count(u,j)`.',
        'Only the seed transformation changes. The graph, support threshold 3, 50 outgoing neighbours, damping 0.85 and personalized dangling-node returns are exactly the original ones.',
        'Power iteration still stops at maximum per-user L1 change <=1e-8, with a 100-iteration cap. Counts are normalized inside the PageRank routine.', '',
        '### B. Log-count regression with the original confidence weights', '',
        '`target(u,i) = log1p(qualified_airing_count(u,i))`, including zero for missing pairs.',
        '`confidence(u,i) = 1 + 20*log1p(count(u,i))` for observations and one for missing pairs.',
        'Optimize:', '',
        '`sum(u,i) confidence(u,i) * (target(u,i)-x(u).T@y(i))^2 + 0.1*(||X||^2+||Y||^2)`.', '',
        'Only the target changes from the original implicit ALS. Repeat strength is now part of the quantity being approximated, not just its confidence.',
        'This is matrix factorization of transformed implicit counts, not a fabricated rating scale or an assertion that counts measure enjoyment.', '',
        '### C. Log-count regression with uniform confidence', '',
        'Keep the same log-count target, factors, solver and regularization, but use `confidence=1` for every observed and missing pair (`alpha=0`).',
        'This is regularized low-rank approximation of the log-count matrix, solved by ALS. It tests whether adding repeat-dependent confidence is needed when repeats already determine the target.',
        'Missing pairs remain in the loss. Setting alpha to zero must not delete observed targets, which are kept separately from confidence.', '',
        'Both MF scores are raw dot products, not probabilities. The objectives differ in target/weighting, so numerical loss values should not be compared across formulations as evidence of better quality.', '',
        '## 4. Results by cohort', '',
        '| Cohort | Users | Current best | Original PPR | Original ALS | Raw-seed PPR | Weighted log-count MF | Uniform log-count MF |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for segment in ['all_target_users', 'template_target_users', 'five_target_users', 'light_history_target_users',
                    'heavy_history_target_users', 'cold_target_users', 'strong_training_favorite_target_users']:
        lines.append(f"| {segment.replace('_', ' ')} | {metrics[segment, 'implicit_als']['users']:,} | "+' | '.join(f"{metrics[segment, m]['map_at_5']:.6f}" for m in NAMES)+' |')
    lines += ['', 'Light/heavy histories are the original 1–10 / >=100 training-airing cohorts.',
        'The new dominant-favorite diagnostic cohort requires a training favorite with >=10 qualified airings, >=50% of the user\'s training airings and availability in the unchanged candidate pool. Count ties use ascending ID. It contains 203 evaluated users.',
        'This definition is training-only and is not used to switch models. The tiny uniform-MF advantage in that one small cohort is not an established overall improvement.', '',
        '### Paired differences', '',
        '| New variant | Reference | Mean AP difference | Paired bootstrap 95% interval |', '|---|---|---:|---|']
    for method in variants:
        for reference, comparison in result['comparisons'][method].items():
            low, high = comparison['paired_bootstrap_95_percent_interval']
            lines.append(f"| {NAMES[method]} | {NAMES[reference]} | {comparison['mean_delta']:+.6f} | [{low:.6f}, {high:.6f}] |")
    lines += ['', 'All intervals use 2,000 paired user-bootstrap resamples, seed 42. They condition on this historical hold-out and do not account for repeated model selection or future temporal uncertainty.', '',
        '## 5. Did the models actually preserve repeated favorites better?', '',
        f'There are **{repeated_total:,} user-target pairs** whose programme had >=10 qualified watches in that user\'s training history. The table counts how many appear in the predicted Top-5.', '',
        '| Method | Repeated target hits | Repeated target recall | Hits absent from own training |', '|---|---:|---:|---:|']
    for method in NAMES:
        d = diagnostics[method]
        lines.append(f"| {NAMES[method]} | {d['repeated_target_hits_training_count_ge_10']:,} / {repeated_total:,} | {d['repeated_target_hits_training_count_ge_10']/repeated_total:.2%} | {d['top5_hits_absent_from_own_training']} |")
    lines += ['',
        'The weighted log-count model almost matches the simple reference at recovering repeated targets. Its overall deficit therefore cannot be described merely as forgetting frequent programmes.',
        'It also finds fewer held-out targets absent from personal training (313 versus 525 for the reference). Uniform MF finds only 216. Better retention does not automatically solve discovery or ranking of weaker histories.',
        'Raw-seed PPR improves repeated-target recovery and MAP, but still allows graph diffusion to reorder direct evidence.', '',
        f'### Dominant-favorite retention: {strong_n} users', '',
        f'Of these training-defined favorites, {relevant_strong_n} also belong to the validation target set. Retaining a training favorite is not automatically a validation hit.', '',
        '| Method | All dominant favorites retained | Relevant dominant favorites retained | Mean rank (missing=6) |',
        '|---|---:|---:|---:|']
    for method in NAMES:
        d = diagnostics[method]
        lines.append(f"| {NAMES[method]} | {d['strong_favorite_retained']} / {strong_n} | {d['relevant_strong_favorite_retained']} / {relevant_strong_n} | {d['strong_favorite_mean_capped_rank']:.3f} |")
    lines += ['', 'This refines the initial diagnosis: original PPR often retained the single dominant favorite but weakened other repeat evidence. Binary ALS had a more substantial repeat-retention failure.', '',
        '## 6. Same two users', '',
        'The heavy/light users are unchanged from the original comparison. The heavy user has a mixed history, so the single favorite is below the >=50% threshold and this user is not in the dominant-favorite cohort.',
        'Titles and categories are original source values. A programme can have positive validation viewing counts without being in the validation top five.', '',
        '| User | Current best | Original PPR | Original ALS | Raw-seed PPR | Weighted log-count MF | Uniform log-count MF |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for example in examples:
        lines.append(f"| {example['label']}: {example['user_id']} | "+' | '.join(f"{example['methods'][m]['ap_at_5']:.6f}" for m in NAMES)+' |')
    lines += ['',
        '**Heavy viewer:** raw-seed PPR moves the 401-watch cartoon from rank five to rank one and improves AP@5 from 0.28 to 0.55. Weighted log-count MF restores repeated cartoons and reaches 0.71 instead of binary ALS\'s 0.00. The simple reference still has 0.76.',
        '**Light viewer:** log-count MF reaches 0.40 versus 0.55 for binary ALS, while both PPR seeds give 0.60. With only one personal watch there is no large repeat-strength distinction to exploit. Gains for frequent viewers do not imply gains for sparse histories.', '']
    for example in examples:
        lines += [f"### {example['label'].title()} viewer `{example['user_id']}`", '',
                  'Validation target IDs: '+' '.join(map(str, example['target_ids']))+'.', '']
        for method in NAMES:
            detail = example['methods'][method]
            lines += [f"**{NAMES[method]} — AP@5={detail['ap_at_5']:.6f}**", '',
                '| Rank | ID | Original title | Category | Training count | Validation count | Target hit |',
                '|---:|---:|---|---|---:|---:|---|']
            for r in detail['recommendations']:
                lines.append(f"| {r['rank']} | {r['tv_show_id']} | {cell(r['title'])} | {cell(r['category'])} | {r['training_count']} | {r['validation_count']} | {'Yes' if r['target_hit'] else 'No'} |")
            lines.append('')
    lines += ['## 7. Current strategy and scope', '',
        '**Retain personal frequency + popularity as the strongest evaluated standalone strategy.** The new experiments substantially reduce the initial gap but do not exceed its primary MAP@5.',
        'The best new PPR variant gives 0.332151, close to raw personal frequency (0.333991) but below the popularity-smoothed reference (0.344131). The best new MF variant overall is uniform log-count MF at 0.330864.',
        'The controlled target change in weighted ALS (same confidence, factors, regularization, iterations and seed) supplies strong evidence that modelling the right repeat-strength target was important in this experiment.',
        'Uniform confidence is slightly better overall than weighted confidence, while weighted confidence is slightly better for the heavy-history cohort. There is no single group-wise winner among the new MF variants.',
        'No switch or fusion involving these variants was implemented; cohort results are diagnostic, not a validated switching policy.', '',
        'Limitations: only one shared historical hold-out, continued model selection on it, incomplete programme IDs, unseen training items without factors/graph support, and no observation of enjoyment. The ten-week horizon still differs from the twelve-week final period.',
        'No unseen test behaviour, Kaggle score, online experiment or revenue effect is used or claimed.', '',
        '## 8. Runtime and verification', '', '| Stage | Seconds |', '|---|---:|']
    for stage, duration in result['timings'].items():
        lines.append(f'| {stage} | {duration:.6f} |')
    lines += ['', f"End-to-end: {result['runtime_seconds']:.3f} s; peak RSS: {result['peak_rss_native_units']/1024**2:.1f} MiB on macOS. BLAS threads=1; seed=42 for factor initialization and bootstrap.",
        'These are single-run wall-clock measurements. The PPR graph was reused exactly; graph construction time is not included again.',
        f"Mathematical tests: **{tests['status']}**, {tests['tests_run']} tests, including dense weighted/uniform regression, both full objectives, decreasing loss, deterministic initialization and analytic raw-seed PPR.",
        f"Independent verification: **{verification['status']}**. {verification['prediction_rows_checked']:,} prediction rows and {verification['cohort_metric_rows_independently_recomputed']} cohort-metric rows checked; repeat-retention diagnostics independently recomputed.",
        'All MF rankings were rebuilt from saved factors; full dense log-count objectives and sampled final-item normal equations were checked independently. Zero-confidence-excess does not erase nonzero regression targets.',
        f"PPR direct linear-system checks: {verification['ppr_direct_linear_solve_users']} users, {verification['ppr_exact_top5_matches']} exact Top-5 matches; maximum saved-score difference {verification['ppr_max_score_difference_from_linear_solution']:.3g}.",
        'Original interaction inputs, targets, reference predictions and PPR transition hashes remained unchanged.', '',
        '## 9. Reproduction and artifacts', '',
        'After the original collaborative comparison has created its graph and reference predictions:', '', '```sh',
        '.venv/bin/python scripts/evaluate_repeat_aware.py',
        '.venv/bin/python scripts/test_repeat_aware_models.py',
        '.venv/bin/python scripts/verify_repeat_aware.py',
        '.venv/bin/python scripts/render_repeat_aware_report.py', '```', '',
        '- `repeat_aware_results.json`: all three fixed configurations, metrics, confidence intervals, repeat diagnostics, convergence and runtime.',
        '- `repeat_aware_metrics.csv`: eight cohorts and six methods, including unchanged historical references.',
        '- `repeat_aware_predictions.csv`: all Top-5 IDs, scores, fallback counts and per-user AP.',
        '- `repeat_aware_examples.json`: the same two users, titles/categories and actual viewing counts.',
        '- `repeat_aware_unit_tests.json`, `repeat_aware_verification.json`: recorded verification results and hashes.',
        '- `data/processed/repeat_aware_models/`: both new factor matrices and explicit user/item mappings.',
        'The implementations use project code with NumPy/SciPy linear algebra and threadpoolctl. No external recommender or pretrained model was used. Code and analysis were AI-assisted in this recorded session.', '']
    (OUT / 'repeat_aware_report.md').write_text('\n'.join(lines))
    print('Wrote reports/repeat_aware_report.md')


if __name__ == '__main__':
    main()
