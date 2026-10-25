# SWEET.TV temporal validation: four recommendation methods

Experiment date: 2026-10-25. This is an offline hold-out experiment, not a Kaggle score or an online test.

## Main result

**Personal frequency wins this hold-out with MAP@5 = 0.333991, versus 0.246637 for popularity.**
The absolute gain is 0.087353; the relative gain over popularity is 35.42%.
The implemented CBF and association-rule configurations do not beat popularity on the primary metric.
One fixed configuration per method was evaluated. There was no validation-based hyperparameter search.

## 1. Time split and reconstructed interactions

- Timezone assumption: **Europe/Kyiv**. Convert log and schedule starts to Unix seconds.
- Training: **2020-03-09 00:00:00 to 2020-05-18 00:00:00**, ISO weeks 11–20.
- Validation: **2020-05-18 00:00:00 to 2020-07-27 00:00:00**, ISO weeks 21–30.
- Schedule end = timezone-aware start + supplied duration in elapsed seconds.
- Match equal channel IDs with positive overlap of half-open intervals.
- Merge all viewing fragments per user and airing by interval union, so duplicate/overlapping logs do not double-count seconds.
- A watched airing has merged overlap / full airing duration **>= 0.8**. Count qualified airings per user and programme ID.
- Exclude zero IDs and nonpositive durations. Exclude entire airings crossing the start, split or end boundary; do not shorten the denominator.
- A log spanning a boundary can contribute only its overlap with eligible airings inside the corresponding window.

There are 316,311 qualified training user-airings and 295,024 validation user-airings.
Fragment merging adds 34,018 and 14,788 qualified user-airings respectively that no individual fragment would qualify.
The timezone-aware elapsed duration matches `duraton` in every log row; mismatches: 0.
The boundary rule excludes 412 labelled airings; this includes airings crossing the overall observation boundaries.

This is a reproducible reconstruction of Kaggle labels, not access to the hidden label-building code. Fragment-merging and tie rules are our explicit choices.

## 2. Candidates, repetitions and leakage control

The common candidate pool has **6,384** nonzero IDs with a positive-duration airing overlapping validation.
It is timestamp-based across both schedule files, including boundary carry-over; it is not just the set of IDs in the second file.
Previously watched items remain eligible for every method. There is no seen-item exclusion.
All interaction statistics, content vocabulary/IDF, user profiles and association rules use training only.
CBF uses descriptions only from airings starting inside the training window. Validation descriptions are used solely to display example titles/categories, never to score items.
The all-user list only supplies row IDs; zero rows for users without training views contribute no behavioural statistics.
Validation viewing counts are loaded by the comparison script only after every model and prediction is fixed.
The weeks 31–42 schedule is not read by this experiment.

There are 2,391 candidates without training metadata and 4,511 without qualified training views.
CBF assigns no positive similarity to candidates without a training feature vector. Rules cannot produce evidence for items with no training viewers.

## 3. Quality calculation

For each user, choose up to five validation programmes by decreasing qualified-airing frequency; ties use ascending programme ID.
These IDs form the relevant set. A predicted item watched outside this top five is not a metric hit.

`AP@5 = sum(P@rank * relevant_at_rank, rank=1..5) / min(5, number_of_targets)`.
`MAP@5 = mean(AP@5 over users with at least one target)`.

Target order determines top-five membership when constructing the label, but standard AP uses relevance membership and prediction ranks, not exact target-rank matching.
The main population is **4,643** users. **271** of 4,914 log users have no qualified validation target and are excluded, not silently assigned zero AP.
Of 1,260 template users, 22 have no local validation target.
All users still receive predictions, including users excluded from MAP.
Target-size distribution: 1 targets: 158 users, 2 targets: 153 users, 3 targets: 134 users, 4 targets: 168 users, 5 targets: 4030 users.

Precision@5 uses five predicted slots; recall@5 divides hits by the target-set size; hit rate@5 measures at least one hit.
The ten-week validation horizon is shorter than the twelve-week final horizon. This is a single historical hold-out, not a final generalization guarantee.

## 4. Implemented methods and exact Top-5 construction

### Popularity

Score = number of distinct training users with a qualified view of the item. Rank candidates by decreasing score, then increasing ID.
Using unique users prevents a single heavy viewer from dominating the global baseline.

### Personal frequency

Score = the user's number of qualified training airings for the programme. Rank positive scores by count, global popularity, then ID.
This directly tests continuation of observed viewing habits. No decay, recency tuning or smoothing is applied.

### Content-based filtering

- Union metadata values per training item. Category weight=2; each distinct genre weight=2; director and actor tokens weight=1; release-decade token weight=0.3.
- Split person fields on commas, semicolons or vertical bars; normalize case and whitespace. Use the first parsed release year to obtain a decade.
- Fit a DictVectorizer and smoothed TF-IDF on the training item catalogue only. TF-IDF IDF is `log((1+n_items)/(1+document_frequency))+1`.
- L2-normalize item vectors. Form each user profile as the sum of watched-item vectors weighted by `log1p(qualified_airing_count)`, then L2-normalize it.
- Score by cosine similarity. Titles and programme identity are not content features. Missing attributes simply omit tokens.
- The fitted content space has 11,880 features.

### Association rules

- One binary basket per training user: items with at least one qualified airing. Count users, not repeated airings, for support.
- For each directed pair A -> B, confidence = users(A and B) / users(A). Remove self-rules.
- Require at least 3 supporting users and confidence >=0.02. Shrink confidence by `support/(support+10)`.
- Keep at most 100 consequents per antecedent by shrunk confidence, breaking ties by item ID.
- Candidate score = sum over the user's watched antecedents of `log1p(personal_count) * shrunk_confidence`.
- There are 120,896 retained directed rules. This is an association model, not sequential next-program prediction.

### Shared list policy

Rank strictly positive method scores, break score ties by training popularity then item ID, take up to five, and fill missing positions from the popularity list while skipping duplicate IDs.
A user with no qualified training interaction receives the same popularity top five under every method. Scores across methods are not calibrated probabilities and are not fused.

## 5. Results

### Primary population

| Method | MAP@5 | Precision@5 | Recall@5 | Hit rate@5 |
|---|---:|---:|---:|---:|
| Popularity | 0.246637 | 0.289726 | 0.307226 | 0.767823 |
| Personal frequency | 0.333991 | 0.378376 | 0.397975 | 0.843636 |
| Content-based filtering | 0.161753 | 0.231790 | 0.246522 | 0.705363 |
| Association rules | 0.242105 | 0.292009 | 0.308087 | 0.780745 |

### MAP@5 by cohort

| Cohort | Users | Popularity | Personal frequency | CBF | Association rules |
|---|---:|---:|---:|---:|---:|
| Five targets | 4,030 | 0.257371 | 0.352388 | 0.164562 | 0.255704 |
| Template with targets | 1,238 | 0.269700 | 0.374024 | 0.174306 | 0.269529 |
| Nonempty training history | 4,539 | 0.248478 | 0.337833 | 0.161648 | 0.243842 |
| Empty training history | 104 | 0.166298 | 0.166298 | 0.166298 | 0.166298 |
| 1–10 training airings | 538 | 0.144728 | 0.141099 | 0.083369 | 0.124303 |
| At least 100 training airings | 995 | 0.296461 | 0.493747 | 0.186941 | 0.303537 |

Cohort boundaries 1–10 and >=100 are descriptive, not tuned switching thresholds. No switching hybrid was evaluated.

### Paired user bootstrap

2,000 paired bootstrap resamples, seed=42. Intervals are conditional on this hold-out, not temporal uncertainty estimates or online-effect evidence.

| Difference in MAP@5 | Mean | 95% interval |
|---|---:|---|
| personal frequency minus popularity | 0.087353 | [0.080843, 0.094078] |
| cbf minus popularity | -0.084885 | [-0.090760, -0.078601] |
| association rules minus popularity | -0.004532 | [-0.006333, -0.002794] |
| cbf minus personal frequency | -0.172238 | [-0.178167, -0.166448] |
| association rules minus personal frequency | -0.091885 | [-0.098921, -0.085007] |

### Recommendation diagnostics

| Method | Distinct recommended items | Mean fallback slots | Fraction previously watched in training |
|---|---:|---:|---:|
| Popularity | 5 | 0.000 | 59.82% |
| Personal frequency | 634 | 0.277 | 94.46% |
| Content-based filtering | 788 | 0.112 | 53.12% |
| Association rules | 16 | 0.112 | 59.17% |

Counts concern the main evaluated population. A popularity baseline is its own method, so its fallback-slot count is recorded as zero.

## 6. Two fixed user examples

Choose the maximum and minimum positive training-airing counts among template users with nonempty validation targets; user ID breaks ties.
Validation-target availability restricts the illustration cohort, but method performance is never used to select examples. The same users appear under all methods.
Titles/categories are representative original schedule values; some titles vary across airings of the same ID. They remain untranslated source data.
`Target hit` means membership in the validation top five. The validation count can be positive even for a target miss.

### Heavy viewer: `10500740270951698446`

Training qualified airings: 904; distinct programmes: 97.

Validation targets:

| ID | Original title | Category | Qualified validation airings |
|---:|---|---|---:|
| 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 198 |
| 12002856 | М/с 'Элвин и бурундуки'. | Детям | 55 |
| 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 43 |
| 2400480 | 'ТСН. Неделя'. | Инфо | 36 |
| 12002355 | М/с 'Кунг-фу панда: Удивительные легенды'. | Детям | 36 |

**Popularity — AP@5=0.200000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 32 | 14 | No |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 7 | 3 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 8 | 2 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 12 | 23 | No |

**Personal frequency — AP@5=0.760000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 198 | Yes |
| 2 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 55 | Yes |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 4 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 18 | No |
| 5 | 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 54 | 43 | Yes |

**Content-based filtering — AP@5=0.066667**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400467 | 'Викна-Новости'. | Инфо | 7 | 3 | No |
| 2 | 5900347 | 'Деньги'. | Инфо | 0 | 1 | No |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 4 | 240081 | Факты. День. | Инфо | 32 | 14 | No |
| 5 | 2500261 | 'Подробности недели'. | Инфо | 0 | 0 | No |

**Association rules — AP@5=0.200000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 36 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 32 | 14 | No |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 7 | 3 | No |
| 4 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 12 | 23 | No |
| 5 | 200344 | 'Чистоnews'. | Развлечения | 8 | 2 | No |

### Light viewer: `12453026253397466416`

Training qualified airings: 1; distinct programmes: 1.

Validation targets:

| ID | Original title | Category | Qualified validation airings |
|---:|---|---|---:|
| 240081 | Факты. День. | Инфо | 9 |
| 2400480 | 'ТСН. Неделя'. | Инфо | 3 |
| 5200303 | 'Следствие вели...' с Леонидом Каневским. | Познавательное | 3 |
| 20088 | 'Завтрак с 1+1'. Информационно-развлекательная программа. | Развлечения | 2 |
| 200337 | 'Утро с 'Интером'. | Развлечения | 1 |

**Popularity — AP@5=0.400000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

**Personal frequency — AP@5=0.600000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200337 | 'Утро с 'Интером'. | Развлечения | 1 | 1 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 3 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 5 | 200344 | 'Чистоnews'. | Развлечения | 0 | 0 | No |

**Content-based filtering — AP@5=0.333333**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 200337 | 'Утро с 'Интером'. | Развлечения | 1 | 1 | Yes |
| 2 | 200477 | 'Завтрак. Выходной'. | Развлечения | 0 | 0 | No |
| 3 | 20088 | 'Завтрак с 1+1'. Информационно-развлекательная программа. | Развлечения | 0 | 2 | Yes |
| 4 | 5900275 | 'Утро России'. | Инфо | 0 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |

**Association rules — AP@5=0.520000**

| Rank | ID | Original title | Category | Training count | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 9 | Yes |
| 3 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1 | No |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 0 | No |
| 5 | 20088 | 'Завтрак с 1+1'. Информационно-развлекательная программа. | Развлечения | 0 | 2 | Yes |

## 7. Interpretation and current strategy

Of 21,688 user-target pairs, 11,789 (54.36%) already appear in that user's qualified training history.
This supports testing continuation of habits; it does not imply that every user is stable or that unseen programmes are irrelevant.

**Heavy viewer:** personal frequency retains the strongly repeated children's programmes and hits four targets, AP@5=0.76. Popularity and association rules mainly recommend news and achieve 0.20.
The CBF profile uses log counts and attribute similarity rather than programme identity; for this mixed-history viewer it ranks news above the dominant repeated cartoon and reaches only 0.066667.
This example illustrates a failure of the implemented content representation, not proof that all content models fail.

**Light viewer:** the single training programme is 200337. Personal frequency keeps it and fills from popularity, reaching AP@5=0.60.
CBF proposes the related morning show 20088, not observed in this user's training history but watched twice in validation; it is a supported example of relevant new-to-observed-history content.
Some other unfamiliar CBF suggestions, such as 200477 and 5900275, have no qualified validation views, so novelty alone is not evidence of useful discovery.
Association rules link the morning programme to widely co-viewed news and another morning programme, giving AP@5=0.52, versus 0.40 for popularity.

Association rules use co-viewing links absent from pure CBF, but confidence tends to favour common consequents.
The measured rules model recommends only 16 distinct items across the evaluated population, close to popularity-driven behaviour; it slightly improves hit rate yet loses MAP because placement matters.
CBF covers more items and can score training-described items with no views, but its coarse/missing attributes and lack of identity persistence are insufficient in this configuration.

**Current choice:** personal frequency with the shared popularity fallback is the strongest implemented strategy on this hold-out, particularly for heavy histories.
For the 1–10-airing cohort it is slightly below popularity, so a history-dependent switch or a hybrid is a reasonable future experiment, not an already measured improvement.
The two required non-baseline algorithms, CBF and association rules, are each independently implemented and evaluated even though the simple baseline wins.

## 8. Limitations

- Only about 10.8% of rows in the first schedule carry an ID; all conclusions concern this labelled subset, not all TV consumption.
- An 80% rule rejects partial viewing; valid fragments must be combined. Long unattended sessions may still qualify and do not reveal enjoyment.
- Removing boundary-crossing airings is conservative but discards observations. The hidden Kaggle pipeline may make different choices.
- CBF deliberately excludes future metadata to respect the strict schedule-use constraint; many validation candidates consequently have no vector.
- Counts reward repeated programmes and frequent airings. A watch is not a rating, causal preference estimate, or satisfaction measure.
- Absence from this platform log is not proof that a user has never seen a programme elsewhere.
- The target top-five cutoff penalizes other programmes the user actually watched; examples explicitly show both kinds of evidence.
- One ten-week hold-out cannot establish twelve-week performance or performance after changes in schedules and user populations.
- No validation hyperparameters were fitted. Selecting a winning method on this hold-out still uses it for model selection; a later temporal test is needed for an independent estimate.
- No Kaggle score, live A/B test, revenue uplift or online effect is claimed.

## 9. Runtime, environment and verification

Preprocessing: 31.327 seconds; peak RSS 222.8 MiB on macOS.
Comparison including evaluation/artifact output: 6.720 seconds; peak RSS 271.3 MiB.

| Stage | Seconds |
|---|---:|
| shared_input_and_training_matrix_seconds | 0.123866 |
| popularity_fit_and_predict_seconds | 0.005616 |
| personal_frequency_fit_and_predict_seconds | 3.018977 |
| cbf_fit_seconds | 0.047472 |
| cbf_predict_seconds | 1.387460 |
| association_rules_fit_seconds | 1.450804 |
| association_rules_predict_seconds | 0.126984 |

Model timings share the separately reported input/matrix construction stage. These are one-run wall-clock measurements, not repeated benchmarks.
The personal-frequency implementation currently scans all candidates in Python; its measured runtime should not be interpreted as inherent algorithmic inferiority to vectorized CBF.

Environment: macOS-27.0.1-arm64-arm-64bit; Python 3.12.11; NumPy 2.5.4; SciPy 1.18.1; scikit-learn 1.9.1.
Model predictions are deterministic; seed=42 is used for bootstrap and verification sampling only.

Independent artifact verification status: **passed**. It checked 19,656 predictions, rebuilt 4,643 targets, independently recomputed 28 MAP rows and recomputed 100 sampled rules from training baskets.
Unit-test status: **passed**, 8 tests for AP semantics, empty targets, deduplicated interval unions, fragment aggregation, DST elapsed time and ranking/fallback. Details: `validation_unit_tests.json`.

## 10. Reproduction and disclosures

See `../README.md` for commands. The full configuration, input hashes, metrics, per-user predictions, targets, retained rules and verification hashes are saved alongside this report.
External packages: NumPy, SciPy and scikit-learn for sparse algebra, TF-IDF and normalization; Python zoneinfo for the system timezone database.
No pretrained model or third-party recommender implementation is used. Recommendations and AP calculations are implemented in this project.
AI-assisted code and analysis are part of this session; retain the corresponding session export for the exam records.
