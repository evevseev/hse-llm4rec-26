# SWEET.TV: bounded parallel hyperparameter search

Experiment date: 2026-10-25. This is an offline model-selection study, not a Kaggle score or online experiment.

## Main conclusion

**Retain personal frequency with a maximum popularity bonus of 3.** It ranks first among the 20 configurations on the original split and first among the frozen finalists on the earlier robustness split.
Primary MAP@5: **0.344131**. Secondary MAP@5: **0.362769**.
Tuning improved some algorithm families but produced no overall improvement over the existing reference.

## 1. Prespecified search budget and ranges

| Family | Tuned values | Unique configurations | Reason |
|---|---|---:|---|
| Personal frequency + popularity | Maximum bonus 0, 1, 3, 6 | 4 | Span no global support through a stronger, still bounded pseudo-count. |
| PPR | Damping 0.5 / 0.85; raw / log1p history | 4 | Check restart strength and preservation of repeats jointly. |
| Log-count MF | 16 / 32 factors; regularization 0.1 / 1; alpha 0 / 20 | 8 | Check capacity, smoothing and extra repeat-dependent confidence. |
| CBF | Raw / log1p history | 2 | Isolate the influence of frequent watched items on the profile. |
| Association rules | Raw / log1p history | 2 | Isolate repeat weights without changing the learned pair rules. |
| **Total** | | **20** | |

The saved `hyperparameter_plan.json` was written before the runs. It contains the full grid, fold definitions, shortlisting rule and conservative final decision rule.
Fixed settings: seed 42; MF target log1p(count), 15 iterations; PPR graph support>=3 and 50 outgoing cosine neighbours; original CBF features/weights and TF-IDF; original support/confidence/shrinkage rules for association mining.
Popularity is a fixed reference and does not consume an additional hyperparameter configuration.
There were **20 unique configurations and 24 fit/prediction runs**: 20 primary plus 4 confirmation reruns of those same settings. No extra settings or seeds were searched.

## 2. Two temporal folds

| Fold | Training | Validation | Target users | Candidates |
|---|---|---|---:|---:|
| Primary | Weeks 11–20, March 9–May 18 | Weeks 21–30, May 18–July 27 | 4,643 | 6,384 |
| Secondary | Weeks 11–16, March 9–April 20 | Weeks 17–20, April 20–May 18 | 4,520 | 4,035 |

All boundaries are 2020 Europe/Kyiv half-open intervals. The validation periods do not overlap.
The secondary fold was reconstructed from raw logs and its schedule. It has its own counts, training metadata, item popularity, candidates and cold-user fallback. The confirmed PPR configurations construct graphs and profiles from this earlier training only; the confirmed frequency models also use only these earlier counts.
CBF, association-rule and MF configurations were outside the frozen shortlist and were not fitted on the secondary fold. Their secondary performance is unknown in this experiment.
Its training metadata uses airings starting before April 20 only. Views after May 18 do not enter its user histories or labels.
Both folds retain the exact join/watch/target protocol: same-channel interval overlap, union of viewing fragments per airing, >=80% coverage, no item zero, boundary-crossing airings excluded, up to five most frequent validation items with ascending-ID ties.
Each method returns five distinct candidate IDs; previously watched items remain eligible. Positive scores are ranked with popularity/ID tie-breaks, then filled from fold-specific training popularity. Cold users receive that same fallback.
MAP@5 averages AP over users with at least one target. Empty-target users are counted separately, not silently scored zero.

**Interpretation limit:** secondary validation is earlier and lies inside the primary training period. Users and histories overlap. This is a cross-period robustness check, not a statistically independent future test.
The horizons also differ (ten validation weeks versus four), so absolute MAP values must not be interpreted as directly comparable difficulty or an improvement from the primary to secondary fold.

## 3. Parallel execution and leakage control

Independent configurations ran in a spawn-based ProcessPoolExecutor, with at most four worker processes and one BLAS thread per worker.
Each configuration fits from scratch with seed 42; no factor warm starts or transfer of fitted parameters between configurations/folds is used. Workers reuse only fold input matrices, never another model or validation labels.
Worker initializers load training counts, training metadata, candidate availability and user IDs only. Predictions are finalized before the coordinator loads validation counts for scoring.
Each run has its own directory, raw predictions, timing/PID record and, for MF, saved factors. Actual overlapping start/end times confirm parallel work.

| Stage | Configurations run | Worker PIDs | Maximum actual concurrent runs | Parallel wall time |
|---|---:|---:|---:|---:|
| Primary | 20 | 4 | 4 | 13.823 s |
| Secondary | 4 | 4 | 4 | 1.799 s |

Secondary raw-data preparation took 26.710 s. Parallel wall times include worker startup and fitting/prediction, but not the subsequent coordinator metric/bootstrap calculations.
Peak RSS in per-run files is the process lifetime peak, not an isolated model allocation or a measured total peak across simultaneous workers.

## 4. All 20 primary configurations

| Rank | Configuration | Family | Parameters | MAP@5 |
|---:|---|---|---|---:|
| 1 | frequency_bonus_3 | Personal frequency + popularity | Maximum popularity bonus=3 | 0.344131 |
| 2 | frequency_bonus_6 | Personal frequency + popularity | Maximum popularity bonus=6 | 0.343806 |
| 3 | ppr_d05_log | Personalized PageRank | damping=0.5, history=log | 0.337132 |
| 4 | ppr_d05_raw | Personalized PageRank | damping=0.5, history=raw | 0.335874 |
| 5 | frequency_bonus_0 | Personal frequency + popularity | Maximum popularity bonus=0 | 0.333991 |
| 6 | frequency_bonus_1 | Personal frequency + popularity | Maximum popularity bonus=1 | 0.333991 |
| 7 | mf_f16_r10_a0 | Log-count matrix factorization | factors=16, regularization=1.0, alpha=0.0 | 0.332706 |
| 8 | mf_f16_r01_a0 | Log-count matrix factorization | factors=16, regularization=0.1, alpha=0.0 | 0.332287 |
| 9 | ppr_d085_raw | Personalized PageRank | damping=0.85, history=raw | 0.332151 |
| 10 | mf_f32_r10_a0 | Log-count matrix factorization | factors=32, regularization=1.0, alpha=0.0 | 0.331687 |
| 11 | mf_f32_r01_a0 | Log-count matrix factorization | factors=32, regularization=0.1, alpha=0.0 | 0.330864 |
| 12 | mf_f32_r10_a20 | Log-count matrix factorization | factors=32, regularization=1.0, alpha=20.0 | 0.327352 |
| 13 | mf_f32_r01_a20 | Log-count matrix factorization | factors=32, regularization=0.1, alpha=20.0 | 0.326813 |
| 14 | mf_f16_r10_a20 | Log-count matrix factorization | factors=16, regularization=1.0, alpha=20.0 | 0.321408 |
| 15 | mf_f16_r01_a20 | Log-count matrix factorization | factors=16, regularization=0.1, alpha=20.0 | 0.321069 |
| 16 | ppr_d085_log | Personalized PageRank | damping=0.85, history=log | 0.316681 |
| 17 | association_rules_log | Association rules | history=log | 0.242105 |
| 18 | association_rules_raw | Association rules | history=raw | 0.220367 |
| 19 | cbf_raw | Content-based filtering | history=raw | 0.202532 |
| 20 | cbf_log | Content-based filtering | history=log | 0.161753 |

### Best configuration within each family

| Family | Best tested parameters | MAP@5 | Confirmed on secondary? |
|---|---|---:|---|
| Personal frequency + popularity | Maximum popularity bonus=3 | 0.344131 | Yes |
| Personalized PageRank | damping=0.5, history=log | 0.337132 | Yes |
| Log-count matrix factorization | factors=16, regularization=1.0, alpha=0.0 | 0.332706 | No; outside frozen top four |
| Association rules | history=log | 0.242105 | No; outside frozen top four |
| Content-based filtering | history=raw | 0.202532 | No; outside frozen top four |

- Frequency bonuses 0 and 1 produced exactly identical ranked lists. Counts are integers, popularity already breaks frequency ties, and a bonus bounded by one does not reverse the observed count ordering here.
- Bonus 6 almost ties bonus 3 on the primary period, but does not improve its mean score.
- PPR benefits from reducing damping to 0.5. At 0.85 raw seeds beat log seeds, but at 0.5 log seeds win: repeat weighting interacts with restart strength, so “raw is always better” is not supported.
- The best MF in this grid uses 16 factors, regularization 1 and uniform confidence. Its improvement over the earlier 32-factor uniform model is small and it remains below the frequency reference.
- Raw history improves CBF over its log-history version, but both remain below popularity. Raw history worsens association-rule ranking in this grid.
- Only the globally top four were shortlisted, as planned. MF, CBF and rules were not evaluated on the secondary fold; no secondary stability claim is made for them.

## 5. Frozen shortlist and secondary results

The top four primary IDs were written to `finalists.json`, with the primary-ranking hash, before any secondary configuration started. The reference was already in the top four, so no fifth confirmation run was necessary.

| Configuration | Primary MAP@5 | Secondary MAP@5 | Primary delta vs bonus 3 | Secondary delta vs bonus 3 |
|---|---:|---:|---:|---:|
| frequency_bonus_3 | 0.344131 | 0.362769 | +0.000000 | +0.000000 |
| frequency_bonus_6 | 0.343806 | 0.359500 | -0.000325 | -0.003269 |
| ppr_d05_log | 0.337132 | 0.354287 | -0.006999 | -0.008482 |
| ppr_d05_raw | 0.335874 | 0.352734 | -0.008257 | -0.010035 |

### Paired uncertainty against the reference

| Configuration | Primary 95% interval for MAP difference | Secondary 95% interval |
|---|---|---|
| frequency_bonus_3 | [+0.000000, +0.000000] | [+0.000000, +0.000000] |
| frequency_bonus_6 | [-0.002107, +0.001467] | [-0.005389, -0.001184] |
| ppr_d05_log | [-0.009386, -0.004664] | [-0.011461, -0.005787] |
| ppr_d05_raw | [-0.010418, -0.006029] | [-0.012887, -0.007303] |

Intervals use 2,000 paired user resamples and seed 42. They are conditional on these folds, are not adjusted for the 20-way model selection and do not establish future-period or causal performance.

### Secondary MAP@5 by cohort

| Cohort | Users | Bonus 3 | Bonus 6 | PPR 0.5/log | PPR 0.5/raw |
|---|---:|---:|---:|---:|---:|
| template target users | 1,202 | 0.397842 | 0.394340 | 0.390265 | 0.387404 |
| five target users | 3,560 | 0.390652 | 0.388426 | 0.379307 | 0.377237 |
| cold target users | 122 | 0.156054 | 0.156054 | 0.156054 | 0.156054 |
| light history target users | 926 | 0.202048 | 0.198970 | 0.184559 | 0.185051 |
| heavy history target users | 354 | 0.592166 | 0.588286 | 0.593173 | 0.594369 |

PPR is slightly above the reference in the smaller secondary heavy-history cohort, but not overall. This post-hoc cohort observation is not a validated switching rule or a reason to change the prespecified global selection.

## 6. Conservative final decision

The saved rule requires a positive mean gain over the reference on both folds and a positive lower bound of the secondary paired 95% interval. Among survivors it chooses the largest minimum fold gain; if none pass, retain bonus 3.
**Selected: `frequency_bonus_3`.** No finalist passed all prespecified robustness checks; retain the reference.
In fact no alternative even has a positive primary mean gain in this grid, and the reference remains first on the secondary period too. The additional period supports retaining it instead of chasing the nearly tied bonus 6.
The selected formula remains:

`score(u,i) = personal_qualified_airing_count(u,i) + 3 * training_viewers(i) / max_candidate_training_viewers`.

The result is not a claim that this is a globally optimal recommendation model; it is the strongest setting in the documented bounded search and has consistent ranking against the shortlisted alternatives on the earlier period.

## 7. Verification

Protocol unit tests: **passed**, 5 tests covering the grid limit, non-overlapping validation periods and rejection of unstable/uncertain candidates.
Independent verification status: **passed**.
- Checked 117,784 user-level lists and independently recomputed 182 cohort-metric rows.
- Reconstructed targets from held-out counts, recomputed every per-user AP and checked all candidate/uniqueness/cold-start constraints.
- Independently rebuilt frequency-based rankings and recomputed the finalists' paired intervals.
- Reconciled all 182,529 secondary training and 133,694 validation qualified airings by projecting the original primary-training event table into the earlier windows.
- Rebuilt secondary candidates and content metadata directly from schedule rows with the correct training cutoff.
- Reproduced 8 previously tested settings' full predictions exactly, including both old PPR seeds, both 32-factor MF confidence choices, CBF, rules and frequency references.
- Verified primary inputs were unchanged, that the shortlist preceded confirmation runs, and that four runs really overlapped in each stage.
- Independently reproduced the final decision. The search verifier checks outputs and fold construction; it does not claim to re-solve every newly fitted latent model independently. Earlier mathematical model tests remain documented in the collaborative/repeat-aware reports.

## 8. Reproduction and artifacts

```sh
.venv/bin/python scripts/search_plan.py
.venv/bin/python scripts/test_search_protocol.py
.venv/bin/python scripts/prepare_search_fold.py
.venv/bin/python scripts/run_hyperparameter_search.py --stage primary
.venv/bin/python scripts/run_hyperparameter_search.py --stage secondary
.venv/bin/python scripts/verify_hyperparameter_search.py
.venv/bin/python scripts/render_search_report.py
```

Original primary processed inputs and previous reference artifacts must exist first; see README.md. The two preparation/primary-search commands can run concurrently because they write separate directories.
- `hyperparameter_plan.json`: frozen grid and fold/selection protocol.
- `hyperparameter_comparison.csv`: all 20 settings, primary metrics/intervals and secondary results where checked.
- `hyperparameter_search/primary/` and `secondary/`: raw/scored predictions, factors where relevant, run metadata, full cohort metrics and rankings.
- `hyperparameter_search/finalists.json`: frozen shortlist and timestamp/hashes.
- `hyperparameter_search/decision.json`: prespecified-rule outcome.
- `search_secondary_preparation.json`: independently prepared earlier fold and provenance.
- `hyperparameter_verification.json` and `search_unit_tests.json`: recorded checks.
The existing limitations remain: only labelled airtime is observable, views are not enjoyment, the final horizon is twelve weeks, and no truly untouched future viewing set is available in the supplied training data.
No final model refit, Kaggle upload, live A/B or revenue claim was made. Project code uses NumPy/SciPy/scikit-learn and threadpoolctl; no external recommender implementation or pretrained model was used. Work was AI-assisted in this recorded session.
