# SWEET.TV: Personalized PageRank and implicit matrix factorization

Experiment date: 2026-10-25. All results are offline validation measurements.

## Main conclusion

**The current personal-frequency + popularity score remains the strongest measured standalone method.**
On the unchanged hold-out, the simple PPR and implicit-ALS configurations do not improve MAP@5.
This is evidence about these implementations and fixed settings, not a claim that all graph models or matrix factorization are inferior.

| Method | MAP@5 | Delta against current best |
|---|---:|---:|
| Personal frequency + popularity | 0.344131 | +0.000000 |
| Personalized PageRank | 0.316681 | -0.027450 |
| Implicit ALS | 0.174112 | -0.170019 |

## 1. Unchanged validation rules

- Training: ISO weeks 11–20, March 9 to May 18, 2020; validation: weeks 21–30, May 18 to July 27, Europe/Kyiv.
- Same channel/interval join, per-user/airing fragment union and >=80% watch threshold; zero IDs and boundary-crossing airings excluded.
- Same 6,384 candidate IDs; repeat recommendations allowed. The same 4,643 users with targets enter primary MAP@5; 271 empty-target users remain excluded.
- Same validation targets: up to five programmes by qualified-airing frequency, with ascending ID for count ties.
- Same positive-score ranking policy: descending score, then training popularity, then ascending ID; fill missing positions with the original popularity order.
- All cold users receive the identical popularity Top-5. No new-user factor or graph profile is inferred from validation.
- Scores from different methods are not fused or treated as viewing probabilities.
- Training graphs and factors use only training interactions. Future schedule supplies candidate availability; no validation metadata or behaviour enters either fit.
- The original best model is read from saved predictions, not refitted or retuned. Hashes confirm the reference and targets are unchanged.

This is a known hold-out already used in previous model selection. One configuration per new algorithm was fixed before running; no validation hyperparameter sweep, early stopping or new hybrid was used.

## 2. Personalized PageRank

### Graph

Let B be the binary training user-item matrix. For each item pair, count distinct common viewers with B.T @ B.
Remove self-edges, require at least three common viewers, and use cosine weight:

`w(i,j) = common_viewers(i,j) / sqrt(viewers(i) * viewers(j))`.

Keep the strongest 50 outgoing neighbours per item, tie-breaking by item ID. The cosine before pruning is symmetric, but independently pruning outgoing rows makes the final graph directed.
Row-normalize retained weights into transition matrix P. Items without outgoing edges are dangling nodes.
The fitted catalogue contains 2,489 training-viewed programmes, 74,332 directed edges and 423 dangling nodes.

### Personalization and iteration

For a warm user, seed mass is proportional to `log1p(personal_qualified_airing_count)` over their training items.
With damping d=0.85, use the row-vector iteration:

`r_next = d * r @ P + ((1-d) + d * dangling_mass(r)) * seed`.

Thus each step either follows a co-view link or restarts at the personal history; dangling mass also returns to that history.
A disconnected seed can retain its mass instead of silently losing probability. Cold users have no seed and directly receive the common fallback.
Stop at maximum per-user L1 step change <=1e-8 or 100 iterations, in batches of 128 users.
All batches converged; iterations ranged from 40 to 42. Graph construction and iteration are deterministic.
Candidate scores are stationary mass. Items absent from the training graph receive zero. This random-walk probability is not the probability that a user will watch the programme.

## 3. Implicit matrix factorization with ALS

Let n(u,i) be a qualified training-airing count. Observed feedback is implicit, not a star rating:

`p(u,i) = 1 if n(u,i)>0 else 0`
`c(u,i) = 1 + 20 * log1p(n(u,i))` for observations, and `1` for missing pairs.

Optimize the weighted implicit objective:

`sum(u,i) c(u,i) * (p(u,i) - x(u).T @ y(i))^2 + 0.1 * (||X||^2 + ||Y||^2)`.

Missing pairs are low-confidence zero-preference targets in this objective, not explicit dislikes. Repeated airings increase confidence but do not change the observed target from one to a frequency.
Settings: **32 factors, 15 full alternating iterations, regularization 0.1, confidence alpha 20, seed 42, float64**.
Initial item factors are normal random values with standard deviation 0.01; user factors initially zero. Solve each weighted least-squares block exactly with Cholesky.
The update includes the all-item Gram matrix, so missing pairs are accounted for rather than being accidentally dropped.
Rank by the raw user-item dot product. It can exceed one or be negative and is not calibrated as a probability. The common positive-score rule handles unscored/negative slots.
No factor is fitted for a programme with no training viewers. Cold user factors are zero, yielding the identical fallback.

The training objective decreased from 2,408,589.576 to 501,674.226; every user/item block decreased it within numerical tolerance.
This checks optimization of the stated training loss, not convergence to a global optimum or maximization of MAP@5.

## 4. Results and comparison with earlier methods

### All implemented standalone methods

| Method | Primary MAP@5 |
|---|---:|
| popularity | 0.246637 |
| personal frequency | 0.333991 |
| cbf | 0.161753 |
| association rules | 0.242105 |
| Personal frequency + popularity | 0.344131 |
| Personalized PageRank | 0.316681 |
| Implicit ALS | 0.174112 |

### Primary secondary metrics

| Method | Precision@5 | Recall@5 | Hit rate@5 |
|---|---:|---:|---:|
| Personal frequency + popularity | 0.388973 | 0.409121 | 0.859358 |
| Personalized PageRank | 0.358777 | 0.378240 | 0.841482 |
| Implicit ALS | 0.243119 | 0.261530 | 0.669179 |

### MAP@5 by cohort

| Cohort | Users | Current best | PPR | Implicit ALS |
|---|---:|---:|---:|---:|
| five target users | 4,030 | 0.362980 | 0.332067 | 0.172553 |
| template target users | 1,238 | 0.384841 | 0.348469 | 0.177085 |
| warm target users | 4,539 | 0.348206 | 0.320126 | 0.174291 |
| cold target users | 104 | 0.166298 | 0.166298 | 0.166298 |
| light history target users | 538 | 0.163011 | 0.145754 | 0.133645 |
| heavy history target users | 995 | 0.497802 | 0.425829 | 0.103571 |

The previously defined light/heavy cohorts mean 1–10 and >=100 qualified training airings. They are descriptive cohorts, not newly tuned switching thresholds.

### Paired comparison against the current best

| New method | Mean AP difference | Paired bootstrap 95% interval | Users improved / worsened / unchanged |
|---|---:|---|---|
| Personalized PageRank | -0.027450 | [-0.030945, -0.023565] | 985 / 1463 / 2195 |
| Implicit ALS | -0.170019 | [-0.177004, -0.162246] | 724 / 2929 / 990 |

Intervals use 2,000 paired user bootstrap samples with seed 42 and condition on this hold-out. They do not account for repeated model selection, future schedule drift or online effects.

## 5. What do graph diffusion and factorization change?

| Method | Catalogue items recommended | Fraction in own training history | Hits absent from own training | Hits added / removed vs current best |
|---|---:|---:|---:|---|
| Personal frequency + popularity | 215 | 83.92% | 525 | 0 / 0 |
| Personalized PageRank | 444 | 87.05% | 440 | 716 / 1417 |
| Implicit ALS | 346 | 62.49% | 703 | 1065 / 4451 |

PPR diffuses from a user's own items through co-view paths. It offers a broader set of items across users, but here the within-user lists are actually more concentrated on previously observed items than the current best.
It finds fewer target hits absent from own training (440 versus 525); graph diffusion is not automatically successful discovery.
ALS supplies more hits absent from own training (703 versus 525), but loses many more existing relevant items overall. Novelty does not compensate for its lower MAP.
Neither collaborative model can score the 4,511 candidates with no training viewers. Of 21,688 user-target pairs, 1,282 concern such unsupported items.
This limitation is distinct from an item being new to a particular user: collaborative models can score the latter when other training users provide evidence.

## 6. Same heavy/light viewer examples

These are the previously fixed users, not newly selected by model performance. Source titles/categories remain in the original language.
Validation counts are shown even for programmes outside the target top five; a positive count alone need not be a MAP hit.

### Heavy viewer: `10500740270951698446`

Qualified training airings: 904.
Validation target IDs: 12001682 12002856 12001697 2400480 12002355.

**Personal frequency + popularity: AP@5=0.760000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |
| 2 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 55 | Yes |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 4 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 18 | No |
| 5 | 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 54 | 43 | Yes |

**Personalized PageRank: AP@5=0.280000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 32 | 14 | No |
| 3 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 12 | 23 | No |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 7 | 3 | No |
| 5 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |

**Implicit ALS: AP@5=0.000000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200477 | 'Завтрак. Выходной'. | Развлечения | 0 | 0 | No |
| 2 | 10002451 | Т/с 'Великолепный векПсы под прикрытием'. | Сериалы | 1 | 0 | No |
| 3 | 200432 | Дизель-шоу. 8 марта. | Развлечения | 3 | 0 | No |
| 4 | 12002107 | М/с 'Аладдин'. | Детям | 0 | 0 | No |
| 5 | 2500413 | Гражданская оборона. | Инфо | 1 | 4 | No |

### Light viewer: `12453026253397466416`

Qualified training airings: 1.
Validation target IDs: 240081 2400480 5200303 20088 200337.

**Personal frequency + popularity: AP@5=0.400000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

**Personalized PageRank: AP@5=0.600000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200337 | 'Утро с 'Интером'. | Развлечения | 1 | 1 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 3 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

**Implicit ALS: AP@5=0.550000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 3 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |
| 4 | 20088 | 'Завтрак с 1+1'. Информационно-развлекательная программа. | Развлечения | 0 | 2 | Yes |
| 5 | 200344 | 'Чистоnews'. | Развлечения | 0 | 0 | No |

### Interpreting the contrast

**Heavy viewer:** the current best preserves the dominant cartoons and has AP@5=0.76. PPR shifts news upwards and has 0.28; ALS has no target hits in its Top-5.
The graph is personalized, but the chosen log-count seed compresses strong frequency differences and the 0.85 diffusion component can reorder favourites through shared neighbours.
For ALS, the heavy viewer's most repeated programme (12001682, 401 qualified training airings) scores 1.028038, below the highest ALS recommendation score 1.466538.
This is consistent with the objective mismatch: observed preferences all target one; counts affect confidence, whereas the competition targets the most frequently viewed programmes.
The example shows a concrete failure of this ALS configuration, not that implicit ALS is mathematically unable to model repeated viewing.

**Light viewer:** PPR keeps the single personal morning-show seed and adds news, reaching AP@5=0.60 versus 0.40 for the current best. ALS reaches 0.55 and supplies another relevant morning show (20088).
Thus useful collaborative information exists for some users despite a negative aggregate result.

### Outcome-selected diagnostics

The following cases deliberately maximize gain/loss against the reference. They are explanations, not representative performance estimates. Full Top-5 IDs, titles, categories and watch counts are saved in `collaborative_examples.json`.

| Selected case | User | Current best AP@5 | PPR AP@5 | ALS AP@5 |
|---|---|---:|---:|---:|
| personalized pagerank largest gain | 14394187406328124815 | 0.000000 | 1.000000 | 1.000000 |
| personalized pagerank largest loss | 11938733505278423840 | 1.000000 | 0.250000 | 0.000000 |
| implicit als largest gain | 11136574438702614386 | 0.000000 | 0.000000 | 1.000000 |
| implicit als largest loss | 10347843425032463307 | 1.000000 | 0.600000 | 0.000000 |

## 7. Answer to the strategy question

**At present we do not lose measured overall quality by retaining personal frequency + popularity instead of replacing it with these two simple collaborative implementations.**
It wins the primary metric, template cohort, light-history cohort and heavy-history cohort. Cold users are identical by construction.
This does not mean collaborative information has no value: PPR and ALS improve individual users and sometimes supply relevant programmes not present in their own history.
No learned switch or fusion using these new models has been evaluated, so the existence of individual gains is not a measured hybrid improvement.
If selecting among the implementations actually tested, retain the current smoothed-frequency model. Do not replace it merely because PageRank or matrix factorization are more sophisticated.

## 8. Limitations and computational cost

- Both methods use one deliberately simple, untuned configuration. Different damping, seed weights, factors, regularization or confidence transformations could change their ranking; none were tested here.
- Decreasing ALS training loss is not a validation objective and does not prove generalization, full convergence or a global optimum.
- Graph pruning, minimum support and missing training items limit PPR coverage. Co-view links capture association, not enjoyment or causality.
- The earlier schedule labelling limitation remains: only about 10.8% of first-file rows have an item ID. Absence from the observed log does not establish that a user never saw a programme.
- The same ten-week hold-out has been inspected repeatedly; conclusions are conditional model-selection evidence, not a fresh independent estimate for the twelve-week test.
- No Kaggle upload, live A/B test, online or revenue claim was made.

| Measured stage | Seconds |
|---|---:|
| shared_input_seconds | 0.115434 |
| ppr_graph_fit_seconds | 0.066190 |
| ppr_predict_seconds | 4.382194 |
| als_fit_seconds | 2.198357 |
| als_predict_seconds | 0.427052 |

End-to-end: 13.294 s; peak RSS: 259.0 MiB on macOS.
BLAS threads were limited to one for reproducibility. These are one-run timings; scoring code is vectorized, so runtime should not be compared as intrinsic algorithmic complexity against earlier Python-loop baselines.
At this scale both new models are feasible. The main reason not to select them now is measured ranking quality, not a demonstrated prohibitive runtime.

## 9. Verification and reproduction

Unit-test status: **passed**, 7 tests. They include an analytic two-node PageRank, personalized dangling-node handling, explicit dense weighted least squares and the full implicit objective.
Independent artifact verification: **passed**, 14,742 prediction rows and 21 cohort-metric rows checked.
All 4,914 ALS rankings were rebuilt from saved factors. A blockwise dense objective equals 501674.226202.
The final ALS item-block normal equations were independently checked for 105 items; maximum relative residual 8.49e-16.
The final user block is not claimed to solve its normal equations after the subsequent item update; this is finite-iteration alternating optimization.
PPR graph rows independently reconstructed: 62. PPR users checked by a sparse linear-system solve instead of power iteration: 32; exact Top-5 matches: 32.
Largest saved PPR score difference from the direct solution: 1.64e-10.

After reproducing the original interaction preparation and best-reference artifacts, run:

```sh
.venv/bin/python scripts/evaluate_collaborative.py
.venv/bin/python scripts/test_collaborative_models.py
.venv/bin/python scripts/verify_collaborative.py
.venv/bin/python scripts/render_collaborative_report.py
```

Artifacts: `collaborative_results.json`, `collaborative_metrics.csv`, `collaborative_predictions.csv`, `collaborative_examples.json`, `collaborative_diagnostics.json`, `collaborative_unit_tests.json`, and `collaborative_verification.json`.
Model artifacts are stored under `data/processed/collaborative_models/`: sparse graph/transition matrices and ALS factors with explicit user/item mappings.
Implementation disclosure: PPR and implicit ALS are implemented in project code; NumPy/SciPy supply linear algebra and threadpoolctl controls BLAS threading. No external recommender implementation or pretrained model was used.
Code and analysis were developed with AI assistance in this recorded session. Keep the corresponding session export for the exam.
