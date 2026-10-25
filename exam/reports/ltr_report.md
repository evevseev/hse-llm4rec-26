# SWEET.TV: learned ranking with history and schedule features

Experiment date: 2026-10-25. One fixed model was trained with supervision ending no later than week 20. Weeks 21–30 were used only for evaluation within this experiment.

## Main result

The history/schedule ranker achieved **MAP@5=0.342860**, versus **0.344131** for the existing personal-frequency + popularity rule.
The paired difference is -0.001271; its conditional 95% bootstrap interval is **[-0.003276, 0.000751]**, including zero.
There is no demonstrated overall gain in this run. The model improves the previously defined heavy-viewer cohort but loses on light histories. No settings were changed after observing outer quality.

## 1. Supervised examples entirely inside the earlier period

A query is one user at one historical prediction cutoff. Features use only qualified airings ending before that cutoff. Labels identify up to five most frequently watched programmes in the next two weeks.

| Query window | Feature history | Label period | Queries | Positive labels | Positives appended during training |
|---|---|---|---:|---:|---:|
| weeks_15_16 | Weeks 11–14 | Weeks 15–16, April 6–20 | 4,081 | 16,469 | 2,155 |
| weeks_17_18 | Weeks 11–16 | Weeks 17–18, April 20–May 4 | 4,132 | 16,545 | 2,779 |
| weeks_19_20 | Weeks 11–18 | Weeks 19–20, May 4–18 | 4,170 | 16,765 | 3,212 |

Total: **12,383 queries**, **1,246,446 user-item rows**, **49,779 positive rows**, **32 features**.
The final label boundary is May 18, exactly when outer validation starts. There are no supervised labels from weeks 21–30 in model fitting.
All three earlier windows are used for training. There is no internal model search or early stopping; the configuration is fixed before fitting.
Labels are binary relevance to the future top five, not binary membership in the training history. A negative label is not evidence of dislike or lack of enjoyment.

History follows the established construction: channel/interval join, per-user/airing interval union, >=80% coverage, nonzero programme IDs and exclusion of boundary-crossing airings.
The richer event export adds the actual channel, airing start/end and merged viewed seconds. All 316,311 training user-airings reconcile with the frozen original training counts.

## 2. Candidate generation and exactly five recommendations

Each user receives 100 natural candidates from labelled programmes available in the prediction schedule:
1. Top 50 by the existing `personal_count + 3 * training_viewers/max_viewers` score.
2. Top 30 by schedule-channel compatibility multiplied by `log1p(future_airings_per_week)`.
3. Top 20 by scheduled airings per week.
4. Deduplicate and fill to 100 by the baseline ordering.
Schedule-channel compatibility is the dot product of the programme's future airing-channel distribution and the user's historical channel share, weighted by qualified viewed seconds.

During training only, missing positive items are appended to their query (8,146 total); each query then has 100–105 items. This is supervised candidate sampling, and the injection flag is never a feature.
Outer prediction never appends positives: candidate selection does not read target behaviour. Every original baseline Top-5 is present in its candidate set, so candidate generation does not remove the reference solution.
For warm users, rank the candidates by the learned margin, tie-break by training popularity and item ID, and output the first five. Negative margins are valid ranking scores; sigmoid-transformed margins are equivalent positive monotone scores, not calibrated viewing probabilities.
Users without qualified history receive exactly the same training-popularity Top-5 as all previous methods. Previously watched programmes remain eligible.

## 3. History and schedule features

| Feature group | Examples and source |
|---|---|
| Personal repetition | Qualified count, log-count, personal share, weekly rate, personal rank. History before the query cutoff only. |
| Recency | Counts in the last and preceding 14 elapsed days, recent trend, days since last qualified item airing. |
| Global evidence | Distinct historical viewers, historical qualified-airing count, weekly rate, viewer fraction. |
| Existing rule | Baseline score and reciprocal baseline rank, computed from the current query history. |
| User context | History volume, distinct items, history calendar days, favorite share, channel concentration. |
| Future availability | Airings per week, fraction of distinct airing-start days, channels, first/last relative position and mean duration. |
| Schedule compatibility | Historical channel share and weekday/four-hour airing-start-slot share matched against the future schedule. |

Only `tv_show_id`, channel, start and duration are read from future schedule rows. Titles, genres, categories, actors and future viewers are not used to score items. Source titles/categories are looked up only for human-readable examples.
Channel and start-time preferences are based on qualified historical viewed seconds, not future activity. The time-slot feature uses the airing start bucket, not a claim to reconstruct every minute of the user's daily viewing.
Calendar-rate and position normalizations reduce differences between two-week training-label windows and ten-week outer availability. They do not eliminate the horizon mismatch.
There are no explicit user/programme ID columns in the feature matrix. IDs identify queries/candidates and break deterministic ties.

## 4. Fixed learning-to-rank implementation

The ranker uses XGBoost `rank:pairwise`: it learns comparisons between relevant and non-relevant items inside the same user/time query.
It is trained on future top-five membership from earlier windows, rather than asking every historically observed item to have the same positive factorization target.

| Parameter | Value |
|---|---|
| objective | rank:pairwise |
| eval_metric | map@5 |
| n_estimators | 120 |
| max_depth | 3 |
| learning_rate | 0.05 |
| min_child_weight | 20 |
| reg_lambda | 1.0 |
| subsample | 1.0 |
| colsample_bytree | 1.0 |
| tree_method | hist |
| max_bin | 64 |
| lambdarank_pair_method | topk |
| lambdarank_num_pair_per_sample | 5 |
| random_state | 42 |
| n_jobs | 4 |

The pairwise objective is a surrogate, not direct maximization of MAP@5. Declaring `map@5` does not mean outer labels are passed to fitting: no eval_set or early stopping is used.
The trained model is saved before outer feature construction. Outer predictions and feature hashes are frozen before the evaluation script opens held-out viewing counts.
The outer period had already been inspected in previous project experiments, and the existing bonus-3 baseline was selected there. Within this new ranker experiment it is evaluation-only; the result is not described as a newly untouched independent test.

## 5. Outer results on weeks 21–30

The target pool, original 4,643 nonempty-target users and AP@5 denominator are unchanged. Predictions are also produced for all 4,914 log users. Cold-user fallback and repeat policy are unchanged.

| Method | MAP@5 | Precision@5 | Recall@5 | Hit rate@5 |
|---|---:|---:|---:|---:|
| History + schedule pairwise ranker | 0.342860 | 0.380616 | 0.399566 | 0.849020 |
| Personal frequency + popularity | 0.344131 | 0.388973 | 0.409121 | 0.859358 |
| Popularity | 0.246637 | 0.289726 | 0.307226 | 0.767823 |

| Cohort | Users | Ranker MAP@5 | Current rule MAP@5 |
|---|---:|---:|---:|
| five target users | 4,030 | 0.362328 | 0.362980 |
| template target users | 1,238 | 0.383266 | 0.384841 |
| warm target users | 4,539 | 0.346905 | 0.348206 |
| cold target users | 104 | 0.166298 | 0.166298 |
| light history target users | 538 | 0.152396 | 0.163011 |
| heavy history target users | 995 | 0.508339 | 0.497802 |

Per-user AP changes: 910 improved, 880 worsened, 2853 unchanged.
The mean difference is -0.001271; 2,000 paired user bootstrap resamples, seed 42, give [-0.003276, 0.000751]. This conditional interval includes zero and does not establish an overall gain or a clear overall loss.
The heavy-history result is descriptive on the previously defined >=100-view cohort; it was not used to fit a new switching threshold or alter the model after evaluation.

## 6. Candidate quality versus ranking quality

Mean target recall in the 100 natural candidates is **80.80%**. This averages the fraction of each user's target set retrieved, not the fraction of all schedule programmes.
A diagnostic oracle that places all retrieved targets first, while retaining the mandatory cold-user fallback, would have MAP@5 **0.797073**.
The oracle uses held-out labels for diagnosis only and is not an implemented recommender or claimed performance. The measured gap shows that ranking errors remain important alongside missing candidates.
The reference Top-5 is present for every user, and therefore the reranking comparison does not benefit from excluding baseline recommendations.

| Method | Catalogue items recommended | Hits absent from own training | Hits for items with no training viewers |
|---|---:|---:|---:|
| History + schedule pairwise ranker | 325 | 516 | 28 |
| Personal frequency + popularity | 215 | 525 | 0 |
| Popularity | 5 | 977 | 0 |

The ranker records 28 user-item target hits for items with no training viewers, whereas the reference records none. Schedule/context features allow such items to be scored without a pre-existing item factor.
This does not establish a causal incremental benefit of schedule features: no feature ablation was selected or evaluated on the outer period.

## 7. What the fitted model uses

Top training split-gain importances:

| Feature | Normalized gain |
|---|---:|
| baseline_rank_reciprocal | 18.71% |
| user_training_airings | 15.96% |
| baseline_score | 14.21% |
| personal_rank_reciprocal | 10.97% |
| future_airings_per_week | 7.21% |
| schedule_channel_affinity | 7.01% |
| recent_14day_count | 4.54% |
| future_first_airing_position | 4.03% |
| days_since_last_item_watch | 3.14% |
| personal_weekly_rate | 2.64% |
| global_viewers | 2.61% |
| personal_share | 2.07% |

Baseline rank/score and user-history volume dominate, while future airing rate and channel compatibility also appear near the top. These are training gain importances, not causal effects, user satisfaction measures or standalone validation improvements.

## 8. Previously fixed user examples

The same heavy/light viewers are retained; original-language titles/categories remain source data. Both examples happen to have unchanged AP relative to the reference, so they are not presented as representative improvements.

### Heavy viewer `10500740270951698446`

Target IDs: 12001682 12002856 12001697 2400480 12002355.
Target IDs retrieved naturally: 2400480 12001682 12001697 12002355 12002856.

**History + schedule pairwise ranker — AP@5=0.760000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |
| 2 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 55 | Yes |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 4 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 18 | No |
| 5 | 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 54 | 43 | Yes |

**Personal frequency + popularity — AP@5=0.760000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |
| 2 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 55 | Yes |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 4 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 18 | No |
| 5 | 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 54 | 43 | Yes |

**Popularity — AP@5=0.200000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 32 | 14 | No |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 7 | 3 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 8 | 2 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 12 | 23 | No |

### Light viewer `12453026253397466416`

Target IDs: 240081 2400480 5200303 20088 200337.
Target IDs retrieved naturally: 20088 200337 240081 2400480 5200303.

**History + schedule pairwise ranker — AP@5=0.400000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 3 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 5 | 700155 | 'Сто к одному'. Телеигра. | Познавательное | 0 | 0 | No |

**Personal frequency + popularity — AP@5=0.400000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

**Popularity — AP@5=0.400000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

## 9. Verification and limitations

Feature tests: **passed**, 6 tests, including invariance to appended future viewing behaviour, boundary handling, time normalization and training-only positive injection.
Artifact verification: **passed**. It reconciled 316,311 qualified historical airings, rebuilt all 49,779 training labels and regenerated 1,246,446 training feature rows from cutoff-bound snapshots.
It also regenerated 491,400 outer feature rows without labels, replayed all model margins and rebuilt all 4,914 Top-5 lists, then independently recomputed 21 cohort-metric rows.
Snapshot regeneration is a reproducibility check using the feature module; separate direct checks compare personal counts/global viewer features to raw historical counts. It is not claimed to be an independent reimplementation of every feature formula.
Frozen original target/reference hashes match. Training-label ends are all <=May 18 and no positive injection occurs at outer prediction.
A first evaluation attempt failed only when serializing a NumPy integer to JSON. The export fix was retried with identical model and prediction hashes; one unique model configuration was evaluated and no parameter/feature selection used the held-out result.

Limitations:
- Training labels cover two-week futures after 4/6/8 weeks of history; outer prediction covers ten future weeks after ten training weeks. Rate normalization does not remove this distribution shift.
- Positive injection makes training candidate sets more complete than natural inference candidates; its sampling bias and the 100-candidate retrieval ceiling remain.
- Only the labelled subset of schedule airtime is observable. >=80% qualified watches do not establish enjoyment or satisfaction.
- This is one fixed ranking model and one known outer period. No post-evaluation tuning or history-dependent hybrid was performed.
- Earlier project decisions used the outer hold-out, so the broader project is not an untouched-test study even though this model's supervised labels/features respect time.
- No Kaggle score, live A/B, revenue or online-effect claim is made.

## 10. Current strategy and reproduction

**Retain the existing personal-frequency + popularity rule as the current global choice.** The learned model nearly matches it and shows useful schedule-aware capability, but has no demonstrated overall MAP improvement in this evaluation.
The requested learned-ranking implementation, model, features and comparisons are saved and reproducible; no additional model was tried against the outer labels.

Training: 11.045 s model fit, 20.042 s including feature/dataset generation; peak RSS 766.4 MiB on macOS.
Successful prediction/evaluation attempt: 9.035 s feature/prediction/export stage, 9.399 s end-to-end; peak RSS 629.5 MiB. Dataset extraction and package installation are excluded.
Environment: Python 3.12.11, macOS-27.0.1-arm64-arm-64bit, XGBoost 3.4.1, NumPy 2.5.4. Seed=42; ranker n_jobs=4; BLAS thread pools controlled separately.

After the original processed/reference artifacts exist:

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

On Apple Silicon macOS this workspace uses a project-local conda-forge llvm-openmp 15.0.5 runtime, stored under ignored `.venv/libomp/`; no system OpenMP installation was changed. Its source URL and archive hash are recorded in `.venv/libomp_source.json`.
Artifacts: `ltr_plan.json`, `ltr_training_queries.csv`, `ltr_training_results.json`, `ltr_feature_importance.json`, `ltr_prediction_manifest.json`, `ltr_predictions.csv`, `ltr_per_user_metrics.csv`, `ltr_metrics.csv`, `ltr_results.json`, `ltr_examples.json`, `ltr_feature_tests.json`, and `ltr_verification.json`.
The saved model is `data/processed/learning_to_rank/ranker.ubj`; training/evaluation feature caches and qualified channel/time history are in the same data directory.
**External implementation disclosure:** XGBoost provides the pairwise boosted-tree ranking algorithm. Feature engineering, temporal sample construction, candidate generation and evaluation are project code. NumPy/SciPy and threadpoolctl provide numeric/runtime support. No pretrained model was used. Work was AI-assisted in this recorded session.
