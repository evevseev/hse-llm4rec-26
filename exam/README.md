# SWEET.TV recommendation experiment

Offline temporal comparison of popularity, personal viewing frequency,
content-based filtering (CBF), association rules, personalized PageRank and
matrix factorization, including repeat-aware variants. Documentation and code are
in English. Original programme titles, categories, names and other source data
remain in their original language.

## Current result

Training: ISO weeks 11–20 of 2020. Validation: weeks 21–30.
On 4,643 users with at least one validation target:

| Method | MAP@5 |
|---|---:|
| **Personal frequency + popularity pseudo-counts** | **0.344131** |
| Learned history/schedule pairwise ranker | 0.342860 |
| PPR, tuned damping 0.5 with log-count personalization | 0.337132 |
| Personal frequency | 0.333991 |
| Log-count MF, tuned 16 factors / regularization 1 / uniform confidence | 0.332706 |
| PPR, raw-count personalization | 0.332151 |
| Log-count MF, uniform confidence | 0.330864 |
| Log-count MF, weighted confidence | 0.326813 |
| Original PPR, log-count personalization | 0.316681 |
| Popularity | 0.246637 |
| Association rules | 0.242105 |
| Original implicit ALS, binary preference | 0.174112 |
| CBF | 0.161753 |

These are local hold-out scores, not Kaggle scores. Read the full methodology,
cohort results, user examples and limitations in
[`reports/validation_report.md`](reports/validation_report.md).

The subsequent [error-analysis and improvement report](reports/frequency_improvement_report.md)
records a failed 28-day recency experiment (MAP@5=0.316302) and the selected
simple extension: `personal_count + 3 * training_viewers / maximum_candidate_training_viewers`.
The selected score improves MAP@5 by 3.04% relative to raw personal frequency on
the same known hold-out. Both experiments are disclosed; no parameter sweep was
run. This is model-selection evidence, not an untouched final estimate.

The later [20-configuration parallel search](reports/hyperparameter_search_report.md)
retains the same frequency + popularity model. Its four frozen finalists were
refitted on weeks 11–16 and checked on weeks 17–20, whose validation period does
not overlap the original weeks 21–30. The reference ranks first on both folds
(0.344131 primary, 0.362769 secondary). The earlier fold is a robustness check,
not a statistically independent future test.

The [learned-ranking experiment](reports/ltr_report.md) uses supervised examples
ending by week 20 and reserves weeks 21–30 for evaluation of one fixed model.
Its MAP@5 is 0.342860 versus 0.344131 for the reference; the paired difference
interval includes zero. It improves heavy-history MAP but does not establish an
overall gain. No outer-label tuning or additional ranking model was tried.

## Setup

Python 3.12 was used. From the project root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Download and extract the competition files into `data/`:
https://www.kaggle.com/competitions/sweettv-tv-program-recommender/data

Expected files:

- `data/dataset11-30.csv`
- `data/export_arh_11-20-final.csv`
- `data/export_arh_21-30-final.csv`
- `data/export_arh_31-42-final.csv` (used by the initial audit, not validation modelling)
- `data/submission.csv`

The previously downloaded archive and extracted files are already present in
this workspace. Input hashes are saved in the audit/preparation JSON files.

## Reproduce the experiment

Run these steps sequentially:

```sh
.venv/bin/python scripts/prepare_validation.py
.venv/bin/python scripts/compare_methods.py
.venv/bin/python scripts/test_validation_logic.py
.venv/bin/python scripts/verify_results.py
.venv/bin/python scripts/render_validation_report.py
```

The preparation script uses only the standard library, creates intermediate
files in `data/processed/`, and removes its disposable SQLite overlap table
after successful aggregation. Allow additional disk space for sorting several
million overlap fragments. It combines viewing fragments by interval union and
uses Europe/Kyiv-aware elapsed time. Airings crossing window boundaries are
excluded rather than partially relabelled.

The comparison script reads training counts, training-only content metadata
and validation item availability first. It builds every model and prediction
before loading validation viewing counts. One fixed configuration per method
is used; no hyperparameter search or hybrid was run in that original comparison. The random seed is 42 for
paired bootstrap and verification sampling; model rankings are deterministic.

To reproduce the earlier naive-time data audit separately:

```sh
.venv/bin/python scripts/audit_data.py
```

That initial audit's pair-level counts differ intentionally from the later
timezone-aware, fragment-merged modelling inputs.

## Reproduce the error analysis and extensions

The original comparison artifacts must exist. Preparation now also exports
`data/processed/training_airings.csv` without changing the original count/target
definitions. Run sequentially:

```sh
.venv/bin/python scripts/prepare_validation.py
.venv/bin/python scripts/analyze_frequency_errors.py
.venv/bin/python scripts/evaluate_recency.py
.venv/bin/python scripts/evaluate_smoothing.py
.venv/bin/python scripts/test_frequency_extensions.py
.venv/bin/python scripts/verify_frequency_extensions.py
.venv/bin/python scripts/render_frequency_report.py
```

The recency half-life (28 days) and smoothing bonus (at most 3 pseudo-views) were
each manually fixed before measuring their respective extension. Smoothing was
tried after recency failed; this sequential use of validation is disclosed in
the report. The independent verifier checks the original artifact hashes,
reconciles all training events with the existing counts, and rebuilds both
extensions' rankings, AP values and cohort metrics.

## Reproduce Personalized PageRank and matrix factorization

The original prepared interactions and selected smoothed-frequency reference
must exist. Both collaborative models use one fixed, untuned configuration:

- PPR: cosine co-view graph, at least 3 common users, 50 outgoing neighbours,
  damping 0.85, log-count personalization, personalized dangling-node returns.
- Implicit ALS: 32 factors, 15 iterations, regularization 0.1,
  confidence `1 + 20*log1p(count)`, seed 42, exact weighted least-squares updates.

```sh
.venv/bin/python scripts/evaluate_collaborative.py
.venv/bin/python scripts/test_collaborative_models.py
.venv/bin/python scripts/verify_collaborative.py
.venv/bin/python scripts/render_collaborative_report.py
```

See [`reports/collaborative_report.md`](reports/collaborative_report.md) for
the comparison, same-user examples, optimization checks and limitations. PPR
and ALS do not beat the current best in these configurations. This is a
statement about tested settings, not an algorithm-family ranking.

The independent verifier reconstructs every ALS rank from saved factors,
evaluates the full dense implicit objective in blocks, checks sampled ALS
normal equations, rebuilds graph rows, and compares sampled personalized
PageRank results with a direct sparse linear solve. It also recomputes all
saved cohort metrics. Original references are protected by SHA-256 checks.

## Reproduce the three repeat-aware variants

The original collaborative graph and saved reference predictions must exist.
The [repeat-aware report](reports/repeat_aware_report.md) records exactly three
fixed experiments motivated by repeated-viewing errors:

1. Replace log-count PPR seeds with raw counts; keep the graph and damping 0.85.
2. Replace binary ALS targets with `log1p(count)`; keep confidence
   `1 + 20*log1p(count)`.
3. Keep `log1p(count)` targets but give every observed/missing pair confidence 1.

Both new MF variants retain 32 factors, 15 iterations, regularization 0.1 and
seed 42. These are matrix factorizations of implicit log-count feedback, not
star-rating models. All original split, target, candidate and fallback rules
remain fixed. No coefficient search or new hybrid is included.

```sh
.venv/bin/python scripts/evaluate_repeat_aware.py
.venv/bin/python scripts/test_repeat_aware_models.py
.venv/bin/python scripts/verify_repeat_aware.py
.venv/bin/python scripts/render_repeat_aware_report.py
```

The variants substantially improve their original model families, but none
beats the current best overall. Preserving repeated targets and finding
relevant programmes absent from personal history are measured separately.
All eight-cohort metrics, favorite-retention diagnostics, factor rankings and
sampled PPR linear solutions are independently verified. This remains model
selection on a previously inspected hold-out, not an independent final test.

## Reproduce the bounded parallel hyperparameter search

The primary processed inputs and previous reference artifacts must exist.
The frozen grid has exactly 20 unique settings: 4 frequency/popularity bonuses,
4 PPR seed/damping combinations, 8 log-count MF settings, 2 CBF history weights
and 2 association-rule history weights. Four primary leaders are frozen before
secondary scoring; confirmation reruns do not introduce new configurations.

```sh
.venv/bin/python scripts/search_plan.py
.venv/bin/python scripts/test_search_protocol.py
.venv/bin/python scripts/prepare_search_fold.py
.venv/bin/python scripts/run_hyperparameter_search.py --stage primary
.venv/bin/python scripts/run_hyperparameter_search.py --stage secondary
.venv/bin/python scripts/verify_hyperparameter_search.py
.venv/bin/python scripts/render_search_report.py
```

The search uses up to four independent worker processes, one BLAS thread each,
seed 42 and no warm starts. Workers do not load validation counts. Each
configuration writes separate prediction/run artifacts; the coordinator scores
them after all fits finish. The secondary fold's metadata, counts and popularity
are rebuilt from its earlier window; every confirmed model uses those inputs.
Only the frozen frequency/PPR finalists were fitted on the secondary fold.
The original primary processed files are preserved.

The selection rule requires positive gains on both folds and a positive lower
secondary paired-bootstrap bound; otherwise retain the existing reference.
Twenty primary fits plus four confirmation fits were performed, with 20 total
unique configurations. See the English report for every setting, timing,
uncertainty interval and the independence limitations of these historical folds.

## Reproduce learned history/schedule ranking

This experiment trains XGBoost `rank:pairwise` on three earlier user/time query
windows: history weeks 11–14 predicts 15–16; 11–16 predicts 17–18; 11–18 predicts
19–20. All labels end by May 18. It uses one fixed model, 32 numeric features,
120 depth-three trees and seed 42, without outer-label early stopping or search.

At prediction, 100 natural candidates combine the existing rule, historical
channel compatibility and scheduled airing frequency. The original rule's
Top-5 is always retained in the candidate set. Future schedule features use
only programme ID, channel, start and duration; future viewing behaviour is
loaded only after model/prediction hashes are frozen.

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/setup_xgboost_openmp.py
.venv/bin/python scripts/prepare_ltr_history.py
.venv/bin/python scripts/test_ltr_features.py
.venv/bin/python scripts/train_ltr.py
.venv/bin/python scripts/evaluate_ltr.py
.venv/bin/python scripts/verify_ltr.py
.venv/bin/python scripts/render_ltr_report.py
```

The OpenMP setup script is optional and specific to Apple Silicon macOS. It
installs a pinned conda-forge runtime under `.venv/`, preserving system state;
`xgboost_runtime.py` loads it before XGBoost. Existing platform runtimes can be
used elsewhere. Runtime provenance is saved in `.venv/libomp_source.json`.

Model and feature artifacts are stored under `data/processed/learning_to_rank/`.
The evaluation script guards against silently changing an already frozen model
or prediction set. One initial JSON-export failure was corrected and retried
with identical model/prediction hashes; it was not a second model experiment.

## Artifacts

- `reports/data_audit.md`: initial data exploration and real interval joins.
- `reports/kaggle_description_notes.md`: official-page excerpts and discrepancies.
- `reports/validation_preparation.json`: split, source hashes, union examples and runtime.
- `data/processed/train_interactions.csv`: qualified training counts.
- `data/processed/validation_interactions.csv`: held-out counts, used only for evaluation.
- `data/processed/training_metadata.json`: training-only item descriptions.
- `data/processed/validation_candidates.json`: the common availability-bounded candidate pool.
- `reports/validation_report.md`: full English comparison report.
- `reports/validation_results.json`: complete configuration, metrics, diagnostics and runtime.
- `reports/validation_metrics.csv`: MAP@5 and secondary metrics by cohort.
- `reports/validation_predictions.csv`: exactly five IDs per log user and method,
  fallback slot counts and AP where defined. **Not a final competition submission.**
- `reports/validation_targets.csv`: reconstructed held-out top-five targets.
- `reports/validation_examples.json`: two common example users for all methods.
- `reports/association_rules.csv`: retained rules with support and confidence.
- `reports/validation_verification.json`: independent checks and artifact hashes.
- `reports/validation_unit_tests.json`: recorded result of the hand-computed logic checks.
- `reports/frequency_improvement_report.md`: error analysis, both attempts and the selected extension.
- `reports/personal_frequency_errors.json`: baseline error and recency diagnostics.
- `reports/smoothed_results.json`: selected score parameters, outcomes and paired comparison.
- `reports/smoothed_predictions.csv`: validation predictions for the selected extension.
- `reports/smoothed_metrics.csv`: original versus smoothed frequency by cohort.
- `reports/smoothed_examples.json`: fixed examples plus largest gain/loss diagnostics.
- `reports/recency_*`: corresponding artifacts for the unsuccessful recency attempt.
- `reports/frequency_extension_verification.json`: independent extension checks and hashes.
- `reports/collaborative_report.md`: PPR and implicit-ALS comparison with the current best.
- `reports/collaborative_results.json`: parameters, convergence, training loss, runtime and metrics.
- `reports/collaborative_predictions.csv`: three methods' Top-5 lists and AP values.
- `reports/collaborative_metrics.csv`: results on the same seven validation cohorts.
- `reports/collaborative_examples.json`: fixed heavy/light users and explicitly outcome-selected diagnostics.
- `reports/collaborative_verification.json`: independent mathematical and artifact checks.
- `data/processed/collaborative_models/`: graph, transition matrix and factor artifacts.
- `reports/repeat_aware_report.md`: three repeat-aware variants and the favorite-retention diagnosis.
- `reports/repeat_aware_results.json`: configurations, metrics, losses, convergence and repeat diagnostics.
- `reports/repeat_aware_metrics.csv`: eight cohorts and six compared methods.
- `reports/repeat_aware_predictions.csv`: unchanged references and three new sets of Top-5 lists.
- `reports/repeat_aware_examples.json`: the same heavy/light users across all six methods.
- `reports/repeat_aware_verification.json`: independent variant checks and frozen-input hashes.
- `data/processed/repeat_aware_models/`: weighted and uniform log-count MF factor artifacts.
- `reports/hyperparameter_search_report.md`: full 20-setting search and cross-period confirmation.
- `reports/hyperparameter_plan.json`: frozen ranges, budget, folds and decision rule.
- `reports/hyperparameter_comparison.csv`: all primary scores and finalist confirmation scores.
- `reports/hyperparameter_search_summary.json`: compact family-best and decision summary.
- `reports/hyperparameter_search/`: per-configuration predictions, factors, timings, metrics and frozen shortlist.
- `reports/hyperparameter_verification.json`: independent fold/metric/parallel-execution checks.
- `data/processed/search_secondary/`: earlier-fold counts, training-only metadata and availability.
- `reports/ltr_report.md`: learned-ranking methodology, outcomes and limits.
- `reports/ltr_plan.json`: fixed parameters, earlier training windows and candidate policy.
- `reports/ltr_training_results.json`: supervised training audit and runtime.
- `reports/ltr_feature_importance.json`: training split-gain feature importances.
- `reports/ltr_prediction_manifest.json`: model/prediction hashes frozen before held-out scoring.
- `reports/ltr_predictions.csv`, `ltr_metrics.csv`, `ltr_results.json`: outer predictions and comparison.
- `reports/ltr_verification.json`: temporal, feature-replay, model-replay and metric checks.
- `data/processed/learning_to_rank/ranker.ubj`: saved XGBoost ranker.

Source data and intermediate data are ignored by `.gitignore`. The report and
implementation are ready to track in a repository; this workspace is not yet
a Git repository. No final model refit, Kaggle upload or exam PDF was performed
in this experiment.

## Sources and implementation disclosure

Official competition data and description are the external data source.
NumPy/SciPy provide sparse algebra; scikit-learn provides vectorization,
TF-IDF and normalization; Python zoneinfo uses the system timezone database.
Earlier recommenders are implemented in project code. The learned-ranking
experiment uses XGBoost's pairwise boosted-tree implementation; its temporal
features, candidate generation and evaluation are project code. No pretrained
model was used. The optional local OpenMP runtime comes from conda-forge.
Code and analysis were developed with AI assistance in this session.
