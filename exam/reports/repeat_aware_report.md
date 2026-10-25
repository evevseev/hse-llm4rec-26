# Repeat-aware PageRank and matrix-factorization variants

Experiment date: 2026-10-25. These are local hold-out results, not Kaggle or online results.

## Main result

**Explicitly modelling repeat strength substantially repairs the collaborative models, especially ALS. None of these three variants beats the current personal-frequency + popularity score overall.**

| Method | Primary MAP@5 | Delta vs current best |
|---|---:|---:|
| Personal frequency + popularity | 0.344131 | +0.000000 |
| Original PPR (log-count seeds) | 0.316681 | -0.027450 |
| Original implicit ALS (binary targets) | 0.174112 | -0.170019 |
| PPR with raw-count seeds | 0.332151 | -0.011980 |
| Log-count MF, weighted confidence | 0.326813 | -0.017318 |
| Log-count MF, uniform confidence | 0.330864 | -0.013267 |

Exactly three variants were specified before running this batch. No further damping, factor-count, regularization or confidence sweep was performed.
The variants were motivated by earlier errors on this same known hold-out; this is model-selection evidence, not an untouched test estimate.

## 1. Why the original models weakened favorites

### PPR compresses frequency and then diffuses it

For the fixed heavy viewer, programme 12001682 had 401 training watches and news programme 2400480 had 62. Their raw frequency ratio is 6.47, but their log1p seed-weight ratio is only 1.45.
The original graph model therefore gives a much weaker relative advantage to the favorite before diffusion even starts. With damping 0.85, only the restart component directly anchors the ranking to these seeds; co-view paths also reshape the scores.
The graph itself counts binary common viewers, so it does not distinguish one from many watches by a particular user when building item links.

**Important qualification:** not every strong favorite was lost. Under the training-only dominant-favorite definition below, original PPR already retained all 203 favorites in Top-5. Its weakness also concerns secondary repeated programmes, ordering and mixed histories.

### Binary-target ALS does not predict viewing frequency

The original model uses `p=1` for any observed pair and changes confidence with `1+20*log1p(count)`. One and 401 watches both ask the dot product to approach one.
Confidence changes the cost of an error, not the target level. A lower-frequency or previously unobserved programme can obtain a higher dot product than a repeated favorite.
This is appropriate for one kind of implicit-preference task but not necessarily for selecting future most-frequent programmes.
The previous independent objective and normal-equation checks passed, so this batch changes the modelling assumptions rather than treating poor MAP as proof of a solver bug.

## 2. Frozen protocol

- Train on weeks 11–20; validate on weeks 21–30. Same Europe/Kyiv timestamp handling and boundary rules.
- Same merged per-user/airing intervals, >=80% watch threshold, qualified-airing counts and exclusion of ID zero.
- Same validation target construction, 6,384 candidates and 4,643 nonempty-target users for primary MAP@5.
- Same allowance for already-watched programmes; same positive-score ordering, popularity/ID tie-breaks and popularity fallback.
- Same cold-user output. No validation behaviour enters training or features.
- Original reference predictions are reused unchanged. The input, target, reference and graph hashes are verified.
- Original 32 factors, 15 iterations, regularization 0.1, initialization and seed 42 remain fixed for both new MF variants.

## 3. Three simple changes

### A. Raw-frequency personalization for PPR

`seed(u,i) = count(u,i) / sum_j count(u,j)`.
Only the seed transformation changes. The graph, support threshold 3, 50 outgoing neighbours, damping 0.85 and personalized dangling-node returns are exactly the original ones.
Power iteration still stops at maximum per-user L1 change <=1e-8, with a 100-iteration cap. Counts are normalized inside the PageRank routine.

### B. Log-count regression with the original confidence weights

`target(u,i) = log1p(qualified_airing_count(u,i))`, including zero for missing pairs.
`confidence(u,i) = 1 + 20*log1p(count(u,i))` for observations and one for missing pairs.
Optimize:

`sum(u,i) confidence(u,i) * (target(u,i)-x(u).T@y(i))^2 + 0.1*(||X||^2+||Y||^2)`.

Only the target changes from the original implicit ALS. Repeat strength is now part of the quantity being approximated, not just its confidence.
This is matrix factorization of transformed implicit counts, not a fabricated rating scale or an assertion that counts measure enjoyment.

### C. Log-count regression with uniform confidence

Keep the same log-count target, factors, solver and regularization, but use `confidence=1` for every observed and missing pair (`alpha=0`).
This is regularized low-rank approximation of the log-count matrix, solved by ALS. It tests whether adding repeat-dependent confidence is needed when repeats already determine the target.
Missing pairs remain in the loss. Setting alpha to zero must not delete observed targets, which are kept separately from confidence.

Both MF scores are raw dot products, not probabilities. The objectives differ in target/weighting, so numerical loss values should not be compared across formulations as evidence of better quality.

## 4. Results by cohort

| Cohort | Users | Current best | Original PPR | Original ALS | Raw-seed PPR | Weighted log-count MF | Uniform log-count MF |
|---|---:|---:|---:|---:|---:|---:|---:|
| all target users | 4,643 | 0.344131 | 0.316681 | 0.174112 | 0.332151 | 0.326813 | 0.330864 |
| template target users | 1,238 | 0.384841 | 0.348469 | 0.177085 | 0.367204 | 0.367991 | 0.367204 |
| five target users | 4,030 | 0.362980 | 0.332067 | 0.172553 | 0.349569 | 0.345616 | 0.349439 |
| light history target users | 538 | 0.163011 | 0.145754 | 0.133645 | 0.146362 | 0.125668 | 0.123326 |
| heavy history target users | 995 | 0.497802 | 0.425829 | 0.103571 | 0.474510 | 0.490638 | 0.486288 |
| cold target users | 104 | 0.166298 | 0.166298 | 0.166298 | 0.166298 | 0.166298 | 0.166298 |
| strong training favorite target users | 203 | 0.460816 | 0.436422 | 0.365757 | 0.438952 | 0.459388 | 0.461006 |

Light/heavy histories are the original 1–10 / >=100 training-airing cohorts.
The new dominant-favorite diagnostic cohort requires a training favorite with >=10 qualified airings, >=50% of the user's training airings and availability in the unchanged candidate pool. Count ties use ascending ID. It contains 203 evaluated users.
This definition is training-only and is not used to switch models. The tiny uniform-MF advantage in that one small cohort is not an established overall improvement.

### Paired differences

| New variant | Reference | Mean AP difference | Paired bootstrap 95% interval |
|---|---|---:|---|
| PPR with raw-count seeds | Personal frequency + popularity | -0.011980 | [-0.014712, -0.009260] |
| PPR with raw-count seeds | Original PPR (log-count seeds) | +0.015470 | [0.013039, 0.017705] |
| Log-count MF, weighted confidence | Personal frequency + popularity | -0.017318 | [-0.020094, -0.014268] |
| Log-count MF, weighted confidence | Original implicit ALS (binary targets) | +0.152701 | [0.145009, 0.159744] |
| Log-count MF, uniform confidence | Personal frequency + popularity | -0.013267 | [-0.016322, -0.010140] |
| Log-count MF, uniform confidence | Original implicit ALS (binary targets) | +0.156752 | [0.149357, 0.163646] |

All intervals use 2,000 paired user-bootstrap resamples, seed 42. They condition on this historical hold-out and do not account for repeated model selection or future temporal uncertainty.

## 5. Did the models actually preserve repeated favorites better?

There are **3,816 user-target pairs** whose programme had >=10 qualified watches in that user's training history. The table counts how many appear in the predicted Top-5.

| Method | Repeated target hits | Repeated target recall | Hits absent from own training |
|---|---:|---:|---:|
| Personal frequency + popularity | 3,739 / 3,816 | 97.98% | 525 |
| Original PPR (log-count seeds) | 3,179 / 3,816 | 83.31% | 440 |
| Original implicit ALS (binary targets) | 1,697 / 3,816 | 44.47% | 703 |
| PPR with raw-count seeds | 3,540 / 3,816 | 92.77% | 459 |
| Log-count MF, weighted confidence | 3,733 / 3,816 | 97.82% | 313 |
| Log-count MF, uniform confidence | 3,643 / 3,816 | 95.47% | 216 |

The weighted log-count model almost matches the simple reference at recovering repeated targets. Its overall deficit therefore cannot be described merely as forgetting frequent programmes.
It also finds fewer held-out targets absent from personal training (313 versus 525 for the reference). Uniform MF finds only 216. Better retention does not automatically solve discovery or ranking of weaker histories.
Raw-seed PPR improves repeated-target recovery and MAP, but still allows graph diffusion to reorder direct evidence.

### Dominant-favorite retention: 203 users

Of these training-defined favorites, 181 also belong to the validation target set. Retaining a training favorite is not automatically a validation hit.

| Method | All dominant favorites retained | Relevant dominant favorites retained | Mean rank (missing=6) |
|---|---:|---:|---:|
| Personal frequency + popularity | 203 / 203 | 181 / 181 | 1.000 |
| Original PPR (log-count seeds) | 203 / 203 | 181 / 181 | 1.049 |
| Original implicit ALS (binary targets) | 186 / 203 | 165 / 181 | 2.192 |
| PPR with raw-count seeds | 203 / 203 | 181 / 181 | 1.000 |
| Log-count MF, weighted confidence | 203 / 203 | 181 / 181 | 1.000 |
| Log-count MF, uniform confidence | 201 / 203 | 181 / 181 | 1.099 |

This refines the initial diagnosis: original PPR often retained the single dominant favorite but weakened other repeat evidence. Binary ALS had a more substantial repeat-retention failure.

## 6. Same two users

The heavy/light users are unchanged from the original comparison. The heavy user has a mixed history, so the single favorite is below the >=50% threshold and this user is not in the dominant-favorite cohort.
Titles and categories are original source values. A programme can have positive validation viewing counts without being in the validation top five.

| User | Current best | Original PPR | Original ALS | Raw-seed PPR | Weighted log-count MF | Uniform log-count MF |
|---|---:|---:|---:|---:|---:|---:|
| heavy: 10500740270951698446 | 0.760000 | 0.280000 | 0.000000 | 0.550000 | 0.710000 | 0.483333 |
| light: 12453026253397466416 | 0.400000 | 0.600000 | 0.550000 | 0.600000 | 0.400000 | 0.400000 |

**Heavy viewer:** raw-seed PPR moves the 401-watch cartoon from rank five to rank one and improves AP@5 from 0.28 to 0.55. Weighted log-count MF restores repeated cartoons and reaches 0.71 instead of binary ALS's 0.00. The simple reference still has 0.76.
**Light viewer:** log-count MF reaches 0.40 versus 0.55 for binary ALS, while both PPR seeds give 0.60. With only one personal watch there is no large repeat-strength distinction to exploit. Gains for frequent viewers do not imply gains for sparse histories.

### Heavy viewer `10500740270951698446`

Validation target IDs: 12001682 12002856 12001697 2400480 12002355.

**Personal frequency + popularity — AP@5=0.760000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |
| 2 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 55 | Yes |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 4 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 18 | No |
| 5 | 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 54 | 43 | Yes |

**Original PPR (log-count seeds) — AP@5=0.280000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 32 | 14 | No |
| 3 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 12 | 23 | No |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 7 | 3 | No |
| 5 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |

**Original implicit ALS (binary targets) — AP@5=0.000000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200477 | 'Завтрак. Выходной'. | Развлечения | 0 | 0 | No |
| 2 | 10002451 | Т/с 'Великолепный векПсы под прикрытием'. | Сериалы | 1 | 0 | No |
| 3 | 200432 | Дизель-шоу. 8 марта. | Развлечения | 3 | 0 | No |
| 4 | 12002107 | М/с 'Аладдин'. | Детям | 0 | 0 | No |
| 5 | 2500413 | Гражданская оборона. | Инфо | 1 | 4 | No |

**PPR with raw-count seeds — AP@5=0.550000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 3 | 240081 | Факты. День. | Инфо | 32 | 14 | No |
| 4 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 55 | Yes |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 12 | 23 | No |

**Log-count MF, weighted confidence — AP@5=0.710000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |
| 2 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 55 | Yes |
| 3 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 18 | No |
| 4 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 5 | 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 54 | 43 | Yes |

**Log-count MF, uniform confidence — AP@5=0.483333**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |
| 2 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 18 | No |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 4 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 55 | Yes |
| 5 | 240081 | Факты. День. | Инфо | 32 | 14 | No |

### Light viewer `12453026253397466416`

Validation target IDs: 240081 2400480 5200303 20088 200337.

**Personal frequency + popularity — AP@5=0.400000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

**Original PPR (log-count seeds) — AP@5=0.600000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200337 | 'Утро с 'Интером'. | Развлечения | 1 | 1 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 3 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

**Original implicit ALS (binary targets) — AP@5=0.550000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 3 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |
| 4 | 20088 | 'Завтрак с 1+1'. Информационно-развлекательная программа. | Развлечения | 0 | 2 | Yes |
| 5 | 200344 | 'Чистоnews'. | Развлечения | 0 | 0 | No |

**PPR with raw-count seeds — AP@5=0.600000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200337 | 'Утро с 'Интером'. | Развлечения | 1 | 1 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 3 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

**Log-count MF, weighted confidence — AP@5=0.400000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200337 | 'Утро с 'Интером'. | Развлечения | 1 | 1 | Yes |
| 2 | 5200303 | 'Следствие вели...' с Леонидом Каневским. | Познавательное | 0 | 3 | Yes |
| 3 | 12002805 | М/с 'Моланг'. | Детям | 0 | 0 | No |
| 4 | 400361 | 'МастерШеф', 7 сезон, 17 эп. | Познавательное | 0 | 0 | No |
| 5 | 200338 | 'Готовим вместе. Домашняя кухня'. | Познавательное | 0 | 0 | No |

**Log-count MF, uniform confidence — AP@5=0.400000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200337 | 'Утро с 'Интером'. | Развлечения | 1 | 1 | Yes |
| 2 | 5200303 | 'Следствие вели...' с Леонидом Каневским. | Познавательное | 0 | 3 | Yes |
| 3 | 500315 | Ток-шоу 'Касается каждого'. | Развлечения | 0 | 0 | No |
| 4 | 5900256 | Утро с Украиной. | Инфо | 0 | 0 | No |
| 5 | 400426 | 'Меняю жену'. | Развлечения | 0 | 0 | No |

## 7. Current strategy and scope

**Retain personal frequency + popularity as the strongest evaluated standalone strategy.** The new experiments substantially reduce the initial gap but do not exceed its primary MAP@5.
The best new PPR variant gives 0.332151, close to raw personal frequency (0.333991) but below the popularity-smoothed reference (0.344131). The best new MF variant overall is uniform log-count MF at 0.330864.
The controlled target change in weighted ALS (same confidence, factors, regularization, iterations and seed) supplies strong evidence that modelling the right repeat-strength target was important in this experiment.
Uniform confidence is slightly better overall than weighted confidence, while weighted confidence is slightly better for the heavy-history cohort. There is no single group-wise winner among the new MF variants.
No switch or fusion involving these variants was implemented; cohort results are diagnostic, not a validated switching policy.

Limitations: only one shared historical hold-out, continued model selection on it, incomplete programme IDs, unseen training items without factors/graph support, and no observation of enjoyment. The ten-week horizon still differs from the twelve-week final period.
No unseen test behaviour, Kaggle score, online experiment or revenue effect is used or claimed.

## 8. Runtime and verification

| Stage | Seconds |
|---|---:|
| shared_input_seconds | 0.123010 |
| ppr_raw_counts_predict_seconds | 4.771610 |
| als_log_counts_weighted_fit_seconds | 2.637149 |
| als_log_counts_weighted_predict_seconds | 0.456012 |
| als_log_counts_uniform_fit_seconds | 2.351840 |
| als_log_counts_uniform_predict_seconds | 0.449328 |

End-to-end: 11.626 s; peak RSS: 268.6 MiB on macOS. BLAS threads=1; seed=42 for factor initialization and bootstrap.
These are single-run wall-clock measurements. The PPR graph was reused exactly; graph construction time is not included again.
Mathematical tests: **passed**, 7 tests, including dense weighted/uniform regression, both full objectives, decreasing loss, deterministic initialization and analytic raw-seed PPR.
Independent verification: **passed**. 29,484 prediction rows and 48 cohort-metric rows checked; repeat-retention diagnostics independently recomputed.
All MF rankings were rebuilt from saved factors; full dense log-count objectives and sampled final-item normal equations were checked independently. Zero-confidence-excess does not erase nonzero regression targets.
PPR direct linear-system checks: 32 users, 32 exact Top-5 matches; maximum saved-score difference 4.48e-11.
Original interaction inputs, targets, reference predictions and PPR transition hashes remained unchanged.

## 9. Reproduction and artifacts

After the original collaborative comparison has created its graph and reference predictions:

```sh
.venv/bin/python scripts/evaluate_repeat_aware.py
.venv/bin/python scripts/test_repeat_aware_models.py
.venv/bin/python scripts/verify_repeat_aware.py
.venv/bin/python scripts/render_repeat_aware_report.py
```

- `repeat_aware_results.json`: all three fixed configurations, metrics, confidence intervals, repeat diagnostics, convergence and runtime.
- `repeat_aware_metrics.csv`: eight cohorts and six methods, including unchanged historical references.
- `repeat_aware_predictions.csv`: all Top-5 IDs, scores, fallback counts and per-user AP.
- `repeat_aware_examples.json`: the same two users, titles/categories and actual viewing counts.
- `repeat_aware_unit_tests.json`, `repeat_aware_verification.json`: recorded verification results and hashes.
- `data/processed/repeat_aware_models/`: both new factor matrices and explicit user/item mappings.
The implementations use project code with NumPy/SciPy linear algebra and threadpoolctl. No external recommender or pretrained model was used. Code and analysis were AI-assisted in this recorded session.
