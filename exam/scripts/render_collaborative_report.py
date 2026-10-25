# Generated with an AI assistant
"""Generate an English comparison from measured collaborative-model artifacts."""
import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT, DATA = ROOT / 'reports', ROOT / 'data' / 'processed'
NAMES = {'smoothed_personal_frequency': 'Personal frequency + popularity',
         'personalized_pagerank': 'Personalized PageRank', 'implicit_als': 'Implicit ALS'}


def load(name):
    return json.loads((OUT / name).read_text())


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def main():
    result = load('collaborative_results.json')
    verification = load('collaborative_verification.json')
    tests = load('collaborative_unit_tests.json')
    original = load('validation_results.json')
    examples = load('collaborative_examples.json')
    rows = {(r['segment'], r['method']): r for r in result['metrics']}
    ref = rows['all_target_users', 'smoothed_personal_frequency']['map_at_5']
    targets = {}
    with (OUT / 'validation_targets.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            targets[row['user_id']] = list(map(int, row['target_ids'].split()))
    factors = np.load(DATA / 'collaborative_models' / 'als_factors.npz', allow_pickle=False)
    users, items = factors['user_ids'].tolist(), factors['item_ids'].tolist()
    item_index, user_index = {i: j for j, i in enumerate(items)}, {u: j for j, u in enumerate(users)}
    supported_targets = sum(i in item_index for t in targets.values() for i in t)
    total_targets = sum(map(len, targets.values()))
    heavy = next(e for e in examples if e['label'] == 'heavy')
    favorite = max(heavy['methods']['smoothed_personal_frequency']['recommendations'], key=lambda r: r['training_count'])
    favorite_score = float(factors['user_factors'][user_index[heavy['user_id']]] @ factors['item_factors'][item_index[favorite['tv_show_id']]])
    ppr_iters = [d['iterations'] for d in result['ppr_convergence']]
    loss = result['als_training_objective']
    diagnostic = {'validation_top5_pairs_with_training_item_factors': supported_targets,
        'validation_top5_pairs_without_any_training_item_view': total_targets-supported_targets,
        'validation_top5_pairs_total': total_targets,
        'heavy_viewer_most_repeated_item': {'user_id': heavy['user_id'], 'tv_show_id': favorite['tv_show_id'],
            'training_count': favorite['training_count'], 'als_score': favorite_score,
            'highest_als_recommendation_score': heavy['methods']['implicit_als']['recommendations'][0]['score']}}
    (OUT / 'collaborative_diagnostics.json').write_text(json.dumps(diagnostic, indent=2)+'\n')
    lines = [
        '# SWEET.TV: Personalized PageRank and implicit matrix factorization', '',
        'Experiment date: 2026-10-25. All results are offline validation measurements.', '',
        '## Main conclusion', '',
        '**The current personal-frequency + popularity score remains the strongest measured standalone method.**',
        'On the unchanged hold-out, the simple PPR and implicit-ALS configurations do not improve MAP@5.',
        'This is evidence about these implementations and fixed settings, not a claim that all graph models or matrix factorization are inferior.', '',
        '| Method | MAP@5 | Delta against current best |', '|---|---:|---:|']
    for method in NAMES:
        value = rows['all_target_users', method]['map_at_5']
        lines.append(f'| {NAMES[method]} | {value:.6f} | {value-ref:+.6f} |')
    lines += ['', '## 1. Unchanged validation rules', '',
        '- Training: ISO weeks 11–20, March 9 to May 18, 2020; validation: weeks 21–30, May 18 to July 27, Europe/Kyiv.',
        '- Same channel/interval join, per-user/airing fragment union and >=80% watch threshold; zero IDs and boundary-crossing airings excluded.',
        '- Same 6,384 candidate IDs; repeat recommendations allowed. The same 4,643 users with targets enter primary MAP@5; 271 empty-target users remain excluded.',
        '- Same validation targets: up to five programmes by qualified-airing frequency, with ascending ID for count ties.',
        '- Same positive-score ranking policy: descending score, then training popularity, then ascending ID; fill missing positions with the original popularity order.',
        '- All cold users receive the identical popularity Top-5. No new-user factor or graph profile is inferred from validation.',
        '- Scores from different methods are not fused or treated as viewing probabilities.',
        '- Training graphs and factors use only training interactions. Future schedule supplies candidate availability; no validation metadata or behaviour enters either fit.',
        '- The original best model is read from saved predictions, not refitted or retuned. Hashes confirm the reference and targets are unchanged.', '',
        'This is a known hold-out already used in previous model selection. One configuration per new algorithm was fixed before running; no validation hyperparameter sweep, early stopping or new hybrid was used.', '',
        '## 2. Personalized PageRank', '',
        '### Graph', '',
        'Let B be the binary training user-item matrix. For each item pair, count distinct common viewers with B.T @ B.',
        'Remove self-edges, require at least three common viewers, and use cosine weight:', '',
        '`w(i,j) = common_viewers(i,j) / sqrt(viewers(i) * viewers(j))`.', '',
        'Keep the strongest 50 outgoing neighbours per item, tie-breaking by item ID. The cosine before pruning is symmetric, but independently pruning outgoing rows makes the final graph directed.',
        'Row-normalize retained weights into transition matrix P. Items without outgoing edges are dangling nodes.',
        f"The fitted catalogue contains {result['model_sizes']['training_items']:,} training-viewed programmes, {result['model_sizes']['graph_directed_edges']:,} directed edges and {result['model_sizes']['graph_dangling_nodes']:,} dangling nodes.", '',
        '### Personalization and iteration', '',
        'For a warm user, seed mass is proportional to `log1p(personal_qualified_airing_count)` over their training items.',
        'With damping d=0.85, use the row-vector iteration:', '',
        '`r_next = d * r @ P + ((1-d) + d * dangling_mass(r)) * seed`.', '',
        'Thus each step either follows a co-view link or restarts at the personal history; dangling mass also returns to that history.',
        'A disconnected seed can retain its mass instead of silently losing probability. Cold users have no seed and directly receive the common fallback.',
        'Stop at maximum per-user L1 step change <=1e-8 or 100 iterations, in batches of 128 users.',
        f"All batches converged; iterations ranged from {min(ppr_iters)} to {max(ppr_iters)}. Graph construction and iteration are deterministic.",
        'Candidate scores are stationary mass. Items absent from the training graph receive zero. This random-walk probability is not the probability that a user will watch the programme.', '',
        '## 3. Implicit matrix factorization with ALS', '',
        'Let n(u,i) be a qualified training-airing count. Observed feedback is implicit, not a star rating:', '',
        '`p(u,i) = 1 if n(u,i)>0 else 0`',
        '`c(u,i) = 1 + 20 * log1p(n(u,i))` for observations, and `1` for missing pairs.', '',
        'Optimize the weighted implicit objective:', '',
        '`sum(u,i) c(u,i) * (p(u,i) - x(u).T @ y(i))^2 + 0.1 * (||X||^2 + ||Y||^2)`.', '',
        'Missing pairs are low-confidence zero-preference targets in this objective, not explicit dislikes. Repeated airings increase confidence but do not change the observed target from one to a frequency.',
        'Settings: **32 factors, 15 full alternating iterations, regularization 0.1, confidence alpha 20, seed 42, float64**.',
        'Initial item factors are normal random values with standard deviation 0.01; user factors initially zero. Solve each weighted least-squares block exactly with Cholesky.',
        'The update includes the all-item Gram matrix, so missing pairs are accounted for rather than being accidentally dropped.',
        'Rank by the raw user-item dot product. It can exceed one or be negative and is not calibrated as a probability. The common positive-score rule handles unscored/negative slots.',
        'No factor is fitted for a programme with no training viewers. Cold user factors are zero, yielding the identical fallback.', '',
        f"The training objective decreased from {loss[0]['training_objective']:,.3f} to {loss[-1]['training_objective']:,.3f}; every user/item block decreased it within numerical tolerance.",
        'This checks optimization of the stated training loss, not convergence to a global optimum or maximization of MAP@5.', '',
        '## 4. Results and comparison with earlier methods', '',
        '### All implemented standalone methods', '', '| Method | Primary MAP@5 |', '|---|---:|']
    for method in ['popularity', 'personal_frequency', 'cbf', 'association_rules']:
        value = next(r['map_at_5'] for r in original['metrics'] if r['segment'] == 'all_target_users' and r['method'] == method)
        lines.append(f"| {method.replace('_', ' ')} | {value:.6f} |")
    for method in NAMES:
        lines.append(f"| {NAMES[method]} | {rows['all_target_users', method]['map_at_5']:.6f} |")
    lines += ['', '### Primary secondary metrics', '',
        '| Method | Precision@5 | Recall@5 | Hit rate@5 |', '|---|---:|---:|---:|']
    for method in NAMES:
        row = rows['all_target_users', method]
        lines.append(f"| {NAMES[method]} | {row['precision_at_5']:.6f} | {row['recall_at_5']:.6f} | {row['hit_rate_at_5']:.6f} |")
    lines += ['', '### MAP@5 by cohort', '', '| Cohort | Users | Current best | PPR | Implicit ALS |', '|---|---:|---:|---:|---:|']
    for segment in ['five_target_users', 'template_target_users', 'warm_target_users', 'cold_target_users',
                    'light_history_target_users', 'heavy_history_target_users']:
        lines.append(f"| {segment.replace('_', ' ')} | {rows[segment, 'implicit_als']['users']:,} | "+' | '.join(f"{rows[segment, m]['map_at_5']:.6f}" for m in NAMES)+' |')
    lines += ['', 'The previously defined light/heavy cohorts mean 1–10 and >=100 qualified training airings. They are descriptive cohorts, not newly tuned switching thresholds.', '',
        '### Paired comparison against the current best', '',
        '| New method | Mean AP difference | Paired bootstrap 95% interval | Users improved / worsened / unchanged |',
        '|---|---:|---|---|']
    for method, values in result['comparisons_vs_smoothed'].items():
        low, high = values['paired_bootstrap_95_percent_interval']
        outcomes = values['user_outcomes']
        lines.append(f"| {NAMES[method]} | {values['mean_delta']:+.6f} | [{low:.6f}, {high:.6f}] | {outcomes.get('improved', 0)} / {outcomes.get('worsened', 0)} / {outcomes.get('unchanged', 0)} |")
    lines += ['', 'Intervals use 2,000 paired user bootstrap samples with seed 42 and condition on this hold-out. They do not account for repeated model selection, future schedule drift or online effects.', '',
        '## 5. What do graph diffusion and factorization change?', '',
        '| Method | Catalogue items recommended | Fraction in own training history | Hits absent from own training | Hits added / removed vs current best |',
        '|---|---:|---:|---:|---|']
    for method in NAMES:
        d = result['recommendation_diagnostics'][method]
        lines.append(f"| {NAMES[method]} | {d['catalogue_items_recommended']} | {d['fraction_recommendations_in_own_training']:.2%} | {d['top5_hits_absent_from_own_training']} | {d['target_hits_added_vs_smoothed']} / {d['target_hits_removed_vs_smoothed']} |")
    lines += ['',
        'PPR diffuses from a user\'s own items through co-view paths. It offers a broader set of items across users, but here the within-user lists are actually more concentrated on previously observed items than the current best.',
        'It finds fewer target hits absent from own training (440 versus 525); graph diffusion is not automatically successful discovery.',
        'ALS supplies more hits absent from own training (703 versus 525), but loses many more existing relevant items overall. Novelty does not compensate for its lower MAP.',
        f"Neither collaborative model can score the {result['model_sizes']['candidates_without_training_history']:,} candidates with no training viewers. Of {total_targets:,} user-target pairs, {total_targets-supported_targets:,} concern such unsupported items.",
        'This limitation is distinct from an item being new to a particular user: collaborative models can score the latter when other training users provide evidence.', '',
        '## 6. Same heavy/light viewer examples', '',
        'These are the previously fixed users, not newly selected by model performance. Source titles/categories remain in the original language.',
        'Validation counts are shown even for programmes outside the target top five; a positive count alone need not be a MAP hit.', '']
    for example in examples[:2]:
        lines += [f"### {example['label'].title()} viewer: `{example['user_id']}`", '',
            f"Qualified training airings: {example['training_qualified_airings']}.",
            'Validation target IDs: '+' '.join(str(r['tv_show_id']) for r in example['targets'])+'.', '']
        for method in NAMES:
            detail = example['methods'][method]
            lines += [f"**{NAMES[method]}: AP@5={detail['ap_at_5']:.6f}**", '',
                '| Rank | ID | Original title | Category | Training count | Validation count | Target hit |',
                '|---:|---:|---|---|---:|---:|---|']
            for r in detail['recommendations']:
                lines.append(f"| {r['rank']} | {r['tv_show_id']} | {cell(r['title'])} | {cell(r['category'])} | {r['training_count']} | {r['validation_count']} | {'Yes' if r['target_hit'] else 'No'} |")
            lines.append('')
    lines += ['### Interpreting the contrast', '',
        '**Heavy viewer:** the current best preserves the dominant cartoons and has AP@5=0.76. PPR shifts news upwards and has 0.28; ALS has no target hits in its Top-5.',
        'The graph is personalized, but the chosen log-count seed compresses strong frequency differences and the 0.85 diffusion component can reorder favourites through shared neighbours.',
        f"For ALS, the heavy viewer\'s most repeated programme ({favorite['tv_show_id']}, {favorite['training_count']} qualified training airings) scores {favorite_score:.6f}, below the highest ALS recommendation score {diagnostic['heavy_viewer_most_repeated_item']['highest_als_recommendation_score']:.6f}.",
        'This is consistent with the objective mismatch: observed preferences all target one; counts affect confidence, whereas the competition targets the most frequently viewed programmes.',
        'The example shows a concrete failure of this ALS configuration, not that implicit ALS is mathematically unable to model repeated viewing.', '',
        '**Light viewer:** PPR keeps the single personal morning-show seed and adds news, reaching AP@5=0.60 versus 0.40 for the current best. ALS reaches 0.55 and supplies another relevant morning show (20088).',
        'Thus useful collaborative information exists for some users despite a negative aggregate result.', '',
        '### Outcome-selected diagnostics', '',
        'The following cases deliberately maximize gain/loss against the reference. They are explanations, not representative performance estimates. Full Top-5 IDs, titles, categories and watch counts are saved in `collaborative_examples.json`.', '',
        '| Selected case | User | Current best AP@5 | PPR AP@5 | ALS AP@5 |', '|---|---|---:|---:|---:|']
    for example in examples[2:]:
        lines.append(f"| {example['label'].replace('_', ' ')} | {example['user_id']} | "+' | '.join(f"{example['methods'][m]['ap_at_5']:.6f}" for m in NAMES)+' |')
    lines += ['', '## 7. Answer to the strategy question', '',
        '**At present we do not lose measured overall quality by retaining personal frequency + popularity instead of replacing it with these two simple collaborative implementations.**',
        'It wins the primary metric, template cohort, light-history cohort and heavy-history cohort. Cold users are identical by construction.',
        'This does not mean collaborative information has no value: PPR and ALS improve individual users and sometimes supply relevant programmes not present in their own history.',
        'No learned switch or fusion using these new models has been evaluated, so the existence of individual gains is not a measured hybrid improvement.',
        'If selecting among the implementations actually tested, retain the current smoothed-frequency model. Do not replace it merely because PageRank or matrix factorization are more sophisticated.', '',
        '## 8. Limitations and computational cost', '',
        '- Both methods use one deliberately simple, untuned configuration. Different damping, seed weights, factors, regularization or confidence transformations could change their ranking; none were tested here.',
        '- Decreasing ALS training loss is not a validation objective and does not prove generalization, full convergence or a global optimum.',
        '- Graph pruning, minimum support and missing training items limit PPR coverage. Co-view links capture association, not enjoyment or causality.',
        '- The earlier schedule labelling limitation remains: only about 10.8% of first-file rows have an item ID. Absence from the observed log does not establish that a user never saw a programme.',
        '- The same ten-week hold-out has been inspected repeatedly; conclusions are conditional model-selection evidence, not a fresh independent estimate for the twelve-week test.',
        '- No Kaggle upload, live A/B test, online or revenue claim was made.', '',
        '| Measured stage | Seconds |', '|---|---:|']
    for stage, duration in result['timings'].items():
        lines.append(f'| {stage} | {duration:.6f} |')
    lines += ['', f"End-to-end: {result['runtime_seconds']:.3f} s; peak RSS: {result['peak_rss_native_units']/1024**2:.1f} MiB on macOS.",
        'BLAS threads were limited to one for reproducibility. These are one-run timings; scoring code is vectorized, so runtime should not be compared as intrinsic algorithmic complexity against earlier Python-loop baselines.',
        'At this scale both new models are feasible. The main reason not to select them now is measured ranking quality, not a demonstrated prohibitive runtime.', '',
        '## 9. Verification and reproduction', '',
        f"Unit-test status: **{tests['status']}**, {tests['tests_run']} tests. They include an analytic two-node PageRank, personalized dangling-node handling, explicit dense weighted least squares and the full implicit objective.",
        f"Independent artifact verification: **{verification['status']}**, {verification['prediction_rows_checked']:,} prediction rows and {verification['metric_rows_independently_recomputed']} cohort-metric rows checked.",
        f"All {verification['als_rankings_rebuilt_from_saved_factors']:,} ALS rankings were rebuilt from saved factors. A blockwise dense objective equals {verification['als_dense_objective']:.6f}.",
        f"The final ALS item-block normal equations were independently checked for {verification['als_item_normal_equations_checked']} items; maximum relative residual {verification['als_max_relative_normal_equation_residual']:.3g}.",
        'The final user block is not claimed to solve its normal equations after the subsequent item update; this is finite-iteration alternating optimization.',
        f"PPR graph rows independently reconstructed: {verification['ppr_graph_rows_independently_rebuilt']}. PPR users checked by a sparse linear-system solve instead of power iteration: {verification['ppr_users_checked_by_linear_solve']}; exact Top-5 matches: {verification['ppr_exact_top5_rank_matches']}.",
        f"Largest saved PPR score difference from the direct solution: {verification['ppr_max_saved_score_vs_linear_solution_difference']:.3g}.", '',
        'After reproducing the original interaction preparation and best-reference artifacts, run:', '', '```sh',
        '.venv/bin/python scripts/evaluate_collaborative.py',
        '.venv/bin/python scripts/test_collaborative_models.py',
        '.venv/bin/python scripts/verify_collaborative.py',
        '.venv/bin/python scripts/render_collaborative_report.py', '```', '',
        'Artifacts: `collaborative_results.json`, `collaborative_metrics.csv`, `collaborative_predictions.csv`, `collaborative_examples.json`, `collaborative_diagnostics.json`, `collaborative_unit_tests.json`, and `collaborative_verification.json`.',
        'Model artifacts are stored under `data/processed/collaborative_models/`: sparse graph/transition matrices and ALS factors with explicit user/item mappings.',
        'Implementation disclosure: PPR and implicit ALS are implemented in project code; NumPy/SciPy supply linear algebra and threadpoolctl controls BLAS threading. No external recommender implementation or pretrained model was used.',
        'Code and analysis were developed with AI assistance in this recorded session. Keep the corresponding session export for the exam.', '']
    (OUT / 'collaborative_report.md').write_text('\n'.join(lines))
    print(json.dumps(diagnostic, indent=2))
    print('Wrote reports/collaborative_report.md')


if __name__ == '__main__':
    main()
