"""Render English search results, all 20 settings and the frozen confirmation."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
SEARCH = OUT / 'hyperparameter_search'
NAMES = {'frequency': 'Personal frequency + popularity', 'ppr': 'Personalized PageRank',
         'mf': 'Log-count matrix factorization', 'cbf': 'Content-based filtering',
         'association_rules': 'Association rules'}


def load(path):
    return json.loads(path.read_text())


def description(config):
    family = config['family']
    if family == 'frequency':
        return f"Maximum popularity bonus={config['bonus']}"
    if family == 'ppr':
        return f"damping={config['damping']}, history={config['history']}"
    if family == 'mf':
        return f"factors={config['factors']}, regularization={config['regularization']}, alpha={config['alpha']}"
    return f"history={config['history']}"


def main():
    plan = load(OUT / 'hyperparameter_plan.json')
    primary = load(SEARCH / 'primary' / 'results.json')
    secondary = load(SEARCH / 'secondary' / 'results.json')
    frozen = load(SEARCH / 'finalists.json')
    decision = load(SEARCH / 'decision.json')
    verification = load(OUT / 'hyperparameter_verification.json')
    tests = load(OUT / 'search_unit_tests.json')
    preparation = load(OUT / 'search_secondary_preparation.json')
    reference = plan['reference_config_id']
    p = {r['id']: r for r in primary['ranking']}
    s = {r['id']: r for r in secondary['ranking']}
    config_by_id = {c['id']: c for c in plan['configurations']}
    pmetrics = {(r['segment'], r['config_id']): r for r in primary['metrics']}
    smetrics = {(r['segment'], r['config_id']): r for r in secondary['metrics']}
    comparison = []
    for row in primary['ranking']:
        key = row['id']
        pc = primary['comparisons_vs_reference'][key]
        sc = secondary['comparisons_vs_reference'].get(key)
        comparison.append({'config_id': key, 'family': row['family'],
            'parameters': description(row), 'primary_map_at_5': row['map_at_5'],
            'primary_delta_vs_reference': pc['mean_delta'],
            'primary_ci_low': pc['paired_bootstrap_95_percent_interval'][0],
            'primary_ci_high': pc['paired_bootstrap_95_percent_interval'][1],
            'secondary_checked': key in s, 'secondary_map_at_5': s[key]['map_at_5'] if key in s else '',
            'secondary_delta_vs_reference': sc['mean_delta'] if sc else '',
            'secondary_ci_low': sc['paired_bootstrap_95_percent_interval'][0] if sc else '',
            'secondary_ci_high': sc['paired_bootstrap_95_percent_interval'][1] if sc else '',
            'selected_by_rule': key == decision['selected_config_id']})
    with (OUT / 'hyperparameter_comparison.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison[0])); writer.writeheader(); writer.writerows(comparison)
    family_bests = {}
    for row in primary['ranking']:
        family_bests.setdefault(row['family'], row)
    lines = [
        '# SWEET.TV: bounded parallel hyperparameter search', '',
        'Experiment date: 2026-10-25. This is an offline model-selection study, not a Kaggle score or online experiment.', '',
        '## Main conclusion', '',
        '**Retain personal frequency with a maximum popularity bonus of 3.** It ranks first among the 20 configurations on the original split and first among the frozen finalists on the earlier robustness split.',
        f"Primary MAP@5: **{p[reference]['map_at_5']:.6f}**. Secondary MAP@5: **{s[reference]['map_at_5']:.6f}**.",
        'Tuning improved some algorithm families but produced no overall improvement over the existing reference.', '',
        '## 1. Prespecified search budget and ranges', '',
        '| Family | Tuned values | Unique configurations | Reason |',
        '|---|---|---:|---|',
        '| Personal frequency + popularity | Maximum bonus 0, 1, 3, 6 | 4 | Span no global support through a stronger, still bounded pseudo-count. |',
        '| PPR | Damping 0.5 / 0.85; raw / log1p history | 4 | Check restart strength and preservation of repeats jointly. |',
        '| Log-count MF | 16 / 32 factors; regularization 0.1 / 1; alpha 0 / 20 | 8 | Check capacity, smoothing and extra repeat-dependent confidence. |',
        '| CBF | Raw / log1p history | 2 | Isolate the influence of frequent watched items on the profile. |',
        '| Association rules | Raw / log1p history | 2 | Isolate repeat weights without changing the learned pair rules. |',
        '| **Total** | | **20** | |', '',
        'The saved `hyperparameter_plan.json` was written before the runs. It contains the full grid, fold definitions, shortlisting rule and conservative final decision rule.',
        'Fixed settings: seed 42; MF target log1p(count), 15 iterations; PPR graph support>=3 and 50 outgoing cosine neighbours; original CBF features/weights and TF-IDF; original support/confidence/shrinkage rules for association mining.',
        'Popularity is a fixed reference and does not consume an additional hyperparameter configuration.',
        f"There were **20 unique configurations and {verification['total_fit_runs']} fit/prediction runs**: 20 primary plus {len(secondary['ranking'])} confirmation reruns of those same settings. No extra settings or seeds were searched.", '',
        '## 2. Two temporal folds', '',
        '| Fold | Training | Validation | Target users | Candidates |', '|---|---|---|---:|---:|',
        f"| Primary | Weeks 11–20, March 9–May 18 | Weeks 21–30, May 18–July 27 | {primary['population']['all_target_users']:,} | {primary['candidate_items']:,} |",
        f"| Secondary | Weeks 11–16, March 9–April 20 | Weeks 17–20, April 20–May 18 | {secondary['population']['all_target_users']:,} | {secondary['candidate_items']:,} |", '',
        'All boundaries are 2020 Europe/Kyiv half-open intervals. The validation periods do not overlap.',
        'The secondary fold was reconstructed from raw logs and its schedule. It has its own counts, training metadata, item popularity, candidates and cold-user fallback. The confirmed PPR configurations construct graphs and profiles from this earlier training only; the confirmed frequency models also use only these earlier counts.',
        'CBF, association-rule and MF configurations were outside the frozen shortlist and were not fitted on the secondary fold. Their secondary performance is unknown in this experiment.',
        'Its training metadata uses airings starting before April 20 only. Views after May 18 do not enter its user histories or labels.',
        'Both folds retain the exact join/watch/target protocol: same-channel interval overlap, union of viewing fragments per airing, >=80% coverage, no item zero, boundary-crossing airings excluded, up to five most frequent validation items with ascending-ID ties.',
        'Each method returns five distinct candidate IDs; previously watched items remain eligible. Positive scores are ranked with popularity/ID tie-breaks, then filled from fold-specific training popularity. Cold users receive that same fallback.',
        'MAP@5 averages AP over users with at least one target. Empty-target users are counted separately, not silently scored zero.', '',
        '**Interpretation limit:** secondary validation is earlier and lies inside the primary training period. Users and histories overlap. This is a cross-period robustness check, not a statistically independent future test.',
        'The horizons also differ (ten validation weeks versus four), so absolute MAP values must not be interpreted as directly comparable difficulty or an improvement from the primary to secondary fold.', '',
        '## 3. Parallel execution and leakage control', '',
        'Independent configurations ran in a spawn-based ProcessPoolExecutor, with at most four worker processes and one BLAS thread per worker.',
        'Each configuration fits from scratch with seed 42; no factor warm starts or transfer of fitted parameters between configurations/folds is used. Workers reuse only fold input matrices, never another model or validation labels.',
        'Worker initializers load training counts, training metadata, candidate availability and user IDs only. Predictions are finalized before the coordinator loads validation counts for scoring.',
        'Each run has its own directory, raw predictions, timing/PID record and, for MF, saved factors. Actual overlapping start/end times confirm parallel work.', '',
        '| Stage | Configurations run | Worker PIDs | Maximum actual concurrent runs | Parallel wall time |',
        '|---|---:|---:|---:|---:|',
        f"| Primary | {len(primary['ranking'])} | {len(primary['worker_pids'])} | {primary['maximum_observed_concurrent_runs']} | {primary['parallel_fit_wall_seconds']:.3f} s |",
        f"| Secondary | {len(secondary['ranking'])} | {len(secondary['worker_pids'])} | {secondary['maximum_observed_concurrent_runs']} | {secondary['parallel_fit_wall_seconds']:.3f} s |", '',
        f"Secondary raw-data preparation took {preparation['runtime_seconds']:.3f} s. Parallel wall times include worker startup and fitting/prediction, but not the subsequent coordinator metric/bootstrap calculations.",
        'Peak RSS in per-run files is the process lifetime peak, not an isolated model allocation or a measured total peak across simultaneous workers.', '',
        '## 4. All 20 primary configurations', '',
        '| Rank | Configuration | Family | Parameters | MAP@5 |', '|---:|---|---|---|---:|']
    for rank, row in enumerate(primary['ranking'], 1):
        lines.append(f"| {rank} | {row['id']} | {NAMES[row['family']]} | {description(row)} | {row['map_at_5']:.6f} |")
    lines += ['', '### Best configuration within each family', '', '| Family | Best tested parameters | MAP@5 | Confirmed on secondary? |', '|---|---|---:|---|']
    for family, row in family_bests.items():
        lines.append(f"| {NAMES[family]} | {description(row)} | {row['map_at_5']:.6f} | {'Yes' if row['id'] in s else 'No; outside frozen top four'} |")
    lines += ['',
        '- Frequency bonuses 0 and 1 produced exactly identical ranked lists. Counts are integers, popularity already breaks frequency ties, and a bonus bounded by one does not reverse the observed count ordering here.',
        '- Bonus 6 almost ties bonus 3 on the primary period, but does not improve its mean score.',
        '- PPR benefits from reducing damping to 0.5. At 0.85 raw seeds beat log seeds, but at 0.5 log seeds win: repeat weighting interacts with restart strength, so “raw is always better” is not supported.',
        '- The best MF in this grid uses 16 factors, regularization 1 and uniform confidence. Its improvement over the earlier 32-factor uniform model is small and it remains below the frequency reference.',
        '- Raw history improves CBF over its log-history version, but both remain below popularity. Raw history worsens association-rule ranking in this grid.',
        '- Only the globally top four were shortlisted, as planned. MF, CBF and rules were not evaluated on the secondary fold; no secondary stability claim is made for them.', '',
        '## 5. Frozen shortlist and secondary results', '',
        'The top four primary IDs were written to `finalists.json`, with the primary-ranking hash, before any secondary configuration started. The reference was already in the top four, so no fifth confirmation run was necessary.', '',
        '| Configuration | Primary MAP@5 | Secondary MAP@5 | Primary delta vs bonus 3 | Secondary delta vs bonus 3 |',
        '|---|---:|---:|---:|---:|']
    for key in frozen['confirmation_ids']:
        lines.append(f"| {key} | {p[key]['map_at_5']:.6f} | {s[key]['map_at_5']:.6f} | {primary['comparisons_vs_reference'][key]['mean_delta']:+.6f} | {secondary['comparisons_vs_reference'][key]['mean_delta']:+.6f} |")
    lines += ['', '### Paired uncertainty against the reference', '',
        '| Configuration | Primary 95% interval for MAP difference | Secondary 95% interval |', '|---|---|---|']
    for key in frozen['confirmation_ids']:
        pc = primary['comparisons_vs_reference'][key]['paired_bootstrap_95_percent_interval']
        sc = secondary['comparisons_vs_reference'][key]['paired_bootstrap_95_percent_interval']
        lines.append(f'| {key} | [{pc[0]:+.6f}, {pc[1]:+.6f}] | [{sc[0]:+.6f}, {sc[1]:+.6f}] |')
    lines += ['', 'Intervals use 2,000 paired user resamples and seed 42. They are conditional on these folds, are not adjusted for the 20-way model selection and do not establish future-period or causal performance.', '',
        '### Secondary MAP@5 by cohort', '', '| Cohort | Users | Bonus 3 | Bonus 6 | PPR 0.5/log | PPR 0.5/raw |', '|---|---:|---:|---:|---:|---:|']
    for segment in ['template_target_users', 'five_target_users', 'cold_target_users', 'light_history_target_users', 'heavy_history_target_users']:
        keys = ['frequency_bonus_3', 'frequency_bonus_6', 'ppr_d05_log', 'ppr_d05_raw']
        lines.append(f"| {segment.replace('_', ' ')} | {smetrics[segment, reference]['users']:,} | "+' | '.join(f"{smetrics[segment, key]['map_at_5']:.6f}" for key in keys)+' |')
    lines += ['',
        'PPR is slightly above the reference in the smaller secondary heavy-history cohort, but not overall. This post-hoc cohort observation is not a validated switching rule or a reason to change the prespecified global selection.', '',
        '## 6. Conservative final decision', '',
        'The saved rule requires a positive mean gain over the reference on both folds and a positive lower bound of the secondary paired 95% interval. Among survivors it chooses the largest minimum fold gain; if none pass, retain bonus 3.',
        f"**Selected: `{decision['selected_config_id']}`.** {decision['reason']}",
        'In fact no alternative even has a positive primary mean gain in this grid, and the reference remains first on the secondary period too. The additional period supports retaining it instead of chasing the nearly tied bonus 6.',
        'The selected formula remains:', '',
        '`score(u,i) = personal_qualified_airing_count(u,i) + 3 * training_viewers(i) / max_candidate_training_viewers`.', '',
        'The result is not a claim that this is a globally optimal recommendation model; it is the strongest setting in the documented bounded search and has consistent ranking against the shortlisted alternatives on the earlier period.', '',
        '## 7. Verification', '',
        f"Protocol unit tests: **{tests['status']}**, {tests['tests_run']} tests covering the grid limit, non-overlapping validation periods and rejection of unstable/uncertain candidates.",
        f"Independent verification status: **{verification['status']}**.",
        f"- Checked {sum(v['prediction_rows_checked'] for v in verification['stages'].values()):,} user-level lists and independently recomputed {sum(v['cohort_metric_rows_recomputed'] for v in verification['stages'].values())} cohort-metric rows.",
        '- Reconstructed targets from held-out counts, recomputed every per-user AP and checked all candidate/uniqueness/cold-start constraints.',
        '- Independently rebuilt frequency-based rankings and recomputed the finalists\' paired intervals.',
        f"- Reconciled all {verification['secondary_qualified_training_airings_reconciled']:,} secondary training and {verification['secondary_qualified_validation_airings_reconciled']:,} validation qualified airings by projecting the original primary-training event table into the earlier windows.",
        '- Rebuilt secondary candidates and content metadata directly from schedule rows with the correct training cutoff.',
        f"- Reproduced {len(verification['previous_configurations_reproduced_exactly'])} previously tested settings\' full predictions exactly, including both old PPR seeds, both 32-factor MF confidence choices, CBF, rules and frequency references.",
        '- Verified primary inputs were unchanged, that the shortlist preceded confirmation runs, and that four runs really overlapped in each stage.',
        '- Independently reproduced the final decision. The search verifier checks outputs and fold construction; it does not claim to re-solve every newly fitted latent model independently. Earlier mathematical model tests remain documented in the collaborative/repeat-aware reports.', '',
        '## 8. Reproduction and artifacts', '', '```sh',
        '.venv/bin/python scripts/search_plan.py',
        '.venv/bin/python scripts/test_search_protocol.py',
        '.venv/bin/python scripts/prepare_search_fold.py',
        '.venv/bin/python scripts/run_hyperparameter_search.py --stage primary',
        '.venv/bin/python scripts/run_hyperparameter_search.py --stage secondary',
        '.venv/bin/python scripts/verify_hyperparameter_search.py',
        '.venv/bin/python scripts/render_search_report.py', '```', '',
        'Original primary processed inputs and previous reference artifacts must exist first; see README.md. The two preparation/primary-search commands can run concurrently because they write separate directories.',
        '- `hyperparameter_plan.json`: frozen grid and fold/selection protocol.',
        '- `hyperparameter_comparison.csv`: all 20 settings, primary metrics/intervals and secondary results where checked.',
        '- `hyperparameter_search/primary/` and `secondary/`: raw/scored predictions, factors where relevant, run metadata, full cohort metrics and rankings.',
        '- `hyperparameter_search/finalists.json`: frozen shortlist and timestamp/hashes.',
        '- `hyperparameter_search/decision.json`: prespecified-rule outcome.',
        '- `search_secondary_preparation.json`: independently prepared earlier fold and provenance.',
        '- `hyperparameter_verification.json` and `search_unit_tests.json`: recorded checks.',
        'The existing limitations remain: only labelled airtime is observable, views are not enjoyment, the final horizon is twelve weeks, and no truly untouched future viewing set is available in the supplied training data.',
        'No final model refit, Kaggle upload, live A/B or revenue claim was made. Project code uses NumPy/SciPy/scikit-learn and threadpoolctl; no external recommender implementation or pretrained model was used. Work was AI-assisted in this recorded session.', '']
    (OUT / 'hyperparameter_search_report.md').write_text('\n'.join(lines))
    summary = {'unique_configurations': 20, 'fit_runs': verification['total_fit_runs'],
        'primary_family_bests': family_bests, 'primary_finalists': frozen['confirmation_ids'],
        'secondary_ranking': secondary['ranking'], 'decision': decision,
        'verification_status': verification['status']}
    (OUT / 'hyperparameter_search_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print('Wrote reports/hyperparameter_search_report.md, hyperparameter_comparison.csv and hyperparameter_search_summary.json')


if __name__ == '__main__':
    main()
