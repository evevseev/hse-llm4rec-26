# Personal-frequency errors and a simple improvement

Experiment date: 2026-10-25. All figures are offline validation results, not Kaggle or online measurements.

## Executive result

**Keep raw personal viewing counts and add a small popularity pseudo-count: MAP@5 rises from 0.333991 to 0.344131.**
Absolute gain: 0.010140; relative gain: 3.04%.
The final extension is one explicit score formula, with no content model, graph or learned blending weight.

**Exploration disclosure:** the first attempted improvement, 28-day recency weighting, reduced MAP@5. After observing this failure, a second fixed experiment added popularity smoothing.
Both experiments are retained. No half-life or smoothing-coefficient grid search was run, but the two approaches were sequentially selected on the same known hold-out.

## 1. What remains fixed

- Training: March 9 to May 18, 2020 (weeks 11–20); validation: May 18 to July 27 (weeks 21–30), Europe/Kyiv.
- Match channels and intervals; union fragments per user/airing; require >=80% of an airing. Exclude zero IDs and boundary-crossing airings.
- Identical training counts, held-out labels, 6,384 candidate IDs, repeat policy and tie-breakers.
- Primary MAP@5 uses the same 4,643 users with targets. Empty-target users are excluded exactly as before.
- Cold users get the same training-popularity Top-5. Missing positions are filled from that same popularity list.
- No validation viewing data enters the scores. Validation was already known when choosing these experiments, so their results are model-selection evidence.
- Adding an export of training airing timestamps to preparation did not change the original predictions/targets/metrics, as checked by artifact hashes.

## 2. Where raw personal frequency makes mistakes

### Missed targets

There are 12,904 missed user-target pairs:
- 9,688 (75.08%) have no qualified training view by that user. Raw frequency cannot score these above zero; only its fallback can introduce them.
- 3,216 were observed in training but were ranked below the five selected items.
“No qualified training view” does not mean the user has never seen the programme; it concerns only this observed platform history and our watch rule.

### False positives

- 11,247 recommended slots have no qualified validation watch.
- 3,184 were actually watched, but fall outside the validation top five and are therefore metric misses.
This distinction matters: a metric miss is not necessarily an irrelevant programme or evidence of dissatisfaction.

| Baseline target hits per user | Users |
|---:|---:|
| 0 | 726 |
| 1 | 1,098 |
| 2 | 1,270 |
| 3 | 1,096 |
| 4 | 407 |
| 5 | 46 |

### Reliability of weak versus repeated personal evidence

| Personal training count of recommended item | Recommended slots | Target-hit fraction |
|---|---:|---:|
| 0 (fallback) | 1,286 | 16.41% |
| 1–2 | 7,470 | 17.24% |
| 3–5 | 5,778 | 32.76% |
| 6–10 | 3,969 | 49.08% |
| >10 | 4,712 | 73.09% |

These are descriptive associations, not causal effects or independently calibrated confidence probabilities.

### Why recency looked plausible

| Latest personal training watch | Recommended slots | Validation Top-5 hit fraction | Any qualified validation watch |
|---|---:|---:|---:|
| last seen over 28 days ago | 6,708 | 20.42% | 29.56% |
| last seen within 28 days | 15,221 | 47.32% | 63.94% |

## 3. Unsuccessful first experiment: recency weighting

`score(u,i) = sum(2 ** (-age_in_days / 28))` over qualified training airings of the item.
Age is measured from airing end to the training cutoff, using elapsed seconds. A four-week half-life was fixed to retain weekly habits while reducing old evidence.
MAP@5 fell to **0.316302** (-0.017688 absolute).
The change added 415 target items to lists but removed 881; 779 users improved and 1385 worsened.
It did remove stale favourites, but that alone was not an effective prediction rule for the next ten weeks. Recency correlations did not establish that discarding older frequency evidence would help.
This experiment is rejected as the current recommendation strategy.

## 4. Selected simple improvement: popularity pseudo-counts

**Score:**

`score(u,i) = personal_qualified_airing_count(u,i) + 3 * viewers_train(i) / max_candidate_viewers_train`.

- `viewers_train(i)` counts distinct training users with a qualified view, matching the original popularity baseline.
- The global favourite receives three pseudo-views; less popular items receive a proportionally smaller bonus.
- Strong personal preferences are retained: an item more than three personal views ahead cannot be overtaken solely by this bounded bonus.
- A globally popular item can enter even if the user has not watched it in the training window, instead of waiting until the personal list has fewer than five items.
- Rank by score, then training popularity, then ascending ID. Allow repeats of previously watched programmes.
- The maximum bonus of 3 was a manually fixed heuristic, not a selected best value from a sweep. No claim is made that it is optimal.
- This is a documented fusion of personal counts and normalized training popularity, not a probability estimate.

## 5. Quality comparison

| Method | Primary MAP@5 |
|---|---:|
| popularity | 0.246637 |
| personal frequency | 0.333991 |
| cbf | 0.161753 |
| association rules | 0.242105 |
| Personal frequency with 28-day decay (rejected) | 0.316302 |
| **Personal frequency + popularity pseudo-counts** | **0.344131** |

| Cohort | Users | Raw personal frequency | Smoothed personal frequency | Delta |
|---|---:|---:|---:|---:|
| all target users | 4,643 | 0.333991 | 0.344131 | +0.010140 |
| five target users | 4,030 | 0.352388 | 0.362980 | +0.010592 |
| template target users | 1,238 | 0.374024 | 0.384841 | +0.010817 |
| cold target users | 104 | 0.166298 | 0.166298 | +0.000000 |
| light history target users | 538 | 0.141099 | 0.163011 | +0.021912 |
| heavy history target users | 995 | 0.493747 | 0.497802 | +0.004054 |
| baseline has stale recommendation | 3,139 | 0.295255 | 0.307821 | +0.012566 |

Paired user-bootstrap 95% interval for the primary MAP gain: **[0.008005, 0.012162]**, 2,000 resamples, seed=42.
This interval conditions on the same hold-out; it does not account for choosing experiments after examining it or for future temporal drift.

Users: 992 improved, 559 worsened, 3,092 have unchanged AP@5.
The smoothed lists gained 609 target items and lost 363 (net +246).
Gained target types: previously observed: 295, no qualified training view: 314.
Lost target types: previously observed: 363.
AP also changes when the same relevant items move within the list, so target-count gain and MAP gain are different quantities.

## 6. Concrete examples and failure cases

The original heavy/light viewers are retained. Two additional examples are deliberately selected by the largest gain/loss to explain behaviour; they are not representative samples.
Titles/categories are representative original schedule values and remain untranslated source data.

### Heavy: `10500740270951698446`

Previously fixed training-volume example.

AP@5: 0.760000 → 0.760000.
Target IDs: 12001682 12002856 12001697 2400480 12002355.

**Raw personal frequency**

| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 402.257 | 198 | Yes |
| 2 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 68.782 | 55 | Yes |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 65.000 | 36 | Yes |
| 4 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 54.647 | 18 | No |
| 5 | 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 54 | 54.170 | 43 | Yes |

**Popularity-smoothed frequency**

| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 401 | 402.257 | 198 | Yes |
| 2 | 12002856 | М/с 'Элвин и бурундуки'. | Детям | 68 | 68.782 | 55 | Yes |
| 3 | 2400480 | 'ТСН. Неделя'. | Инфо | 62 | 65.000 | 36 | Yes |
| 4 | 12001734 | М/с 'Волшебные покровители', 154 с. 'Хочу это вырезать / Мэрский день'. | Детям | 54 | 54.647 | 18 | No |
| 5 | 12001697 | М/с 'Аватар: Легенда об Аанге', 56 с. 'Южные захватчики'. | Детям | 54 | 54.170 | 43 | Yes |

### Light: `12453026253397466416`

Previously fixed training-volume example.

AP@5: 0.600000 → 0.400000.
Target IDs: 240081 2400480 5200303 20088 200337.

**Raw personal frequency**

| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 200337 | 'Утро с 'Интером'. | Развлечения | 1 | 1.795 | 1 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3.000 | 3 | Yes |
| 3 | 240081 | Факты. День. | Инфо | 0 | 2.746 | 9 | Yes |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 2.013 | 0 | No |
| 5 | 200344 | 'Чистоnews'. | Развлечения | 0 | 1.860 | 0 | No |

**Popularity-smoothed frequency**

| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3.000 | 3 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 2.746 | 9 | Yes |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 2.013 | 0 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 0 | 1.860 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1.838 | 1 | No |

### Largest Gain: `11938733505278423840`

Outcome-selected diagnostic: largest AP gain; not a representative sample.

AP@5: 0.200000 → 1.000000.
Target IDs: 2400480.

**Raw personal frequency**

| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 6200371 | 'ДжеДАИ'. | Познавательное | 1 | 1.809 | 0 | No |
| 2 | 90076628 | Х/ф 'Я, Франкенштейн'. | Фильмы | 1 | 1.075 | 0 | No |
| 3 | 90074351 | Х/ф 'Маркиз'. | Фильмы | 1 | 1.019 | 0 | No |
| 4 | 90081459 | Х/ф 'Убийца 2. Против всех'. | Фильмы | 1 | 1.003 | 0 | No |
| 5 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3.000 | 1 | Yes |

**Popularity-smoothed frequency**

| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3.000 | 1 | Yes |
| 2 | 240081 | Факты. День. | Инфо | 0 | 2.746 | 0 | No |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 2.013 | 0 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 0 | 1.860 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1.838 | 0 | No |

### Largest Loss: `14394187406328124815`

Outcome-selected diagnostic: largest AP loss; not a representative sample.

AP@5: 1.000000 → 0.000000.
Target IDs: 1000376.

**Raw personal frequency**

| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 1000376 | Т/с 'Друзья', 1 сезон, 1-3 с. | Сериалы | 1 | 1.249 | 2 | Yes |
| 2 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3.000 | 0 | No |
| 3 | 240081 | Факты. День. | Инфо | 0 | 2.746 | 0 | No |
| 4 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 2.013 | 0 | No |
| 5 | 200344 | 'Чистоnews'. | Развлечения | 0 | 1.860 | 0 | No |

**Popularity-smoothed frequency**

| Rank | ID | Original title | Category | Personal count | Smoothed score | Validation count | Target hit |
|---:|---:|---|---|---:|---:|---:|---|
| 1 | 2400480 | 'ТСН. Неделя'. | Инфо | 0 | 3.000 | 0 | No |
| 2 | 240081 | Факты. День. | Инфо | 0 | 2.746 | 0 | No |
| 3 | 2400467 | 'Викна-Новости'. | Инфо | 0 | 2.013 | 0 | No |
| 4 | 200344 | 'Чистоnews'. | Развлечения | 0 | 1.860 | 0 | No |
| 5 | 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо | 0 | 1.838 | 0 | No |

The original heavy viewer retains AP@5=0.76: strong repeated cartoon preferences survive the bounded bonus.
The original light viewer is a useful counterexample to the average gain: inspect the table rather than assuming every sparse user improves. Popularity can push a genuinely relevant, less popular personal favourite down.
The largest-loss example makes this failure explicit. A positive average gain does not remove individual regressions.

## 7. Recommendation and limits

**Use the popularity-smoothed personal-frequency score as the current offline choice.** It improves the measured MAP while retaining a simple explanation: personal repetition plus limited shared evidence.
The implementation needs only training user-item counts and item viewer counts; no extra content or collaborative model is required for the selected score. The training timestamps were needed only for diagnosis and the rejected recency experiment.
It remains popularity-biased, can hurt unusual preferences, and has no positive evidence for items with neither personal nor global training views. Only the labelled subset of TV airtime is observable.
The known validation set was used for error analysis and to choose a second experiment after a failed first attempt. A later untouched temporal window would be needed for an independent quality estimate. No A/B, revenue or Kaggle result is claimed.

## 8. Runtime and checks

Smoothed experiment: fit/input-event processing 0.492 s, prediction 9.910 s, end-to-end 10.754 s; peak RSS 199.2 MiB on macOS.
The two variants were rerun concurrently after a memory-only implementation adjustment; these wall-clock times are not controlled performance benchmarks.
Verification status: **passed**. All 316,311 training-airing events reconcile with the original counts.
An independent standard-library verifier rebuilt all 4,914 rankings and 4,643 per-user AP values for each extension, checked all cohort metric rows, and confirmed that original prediction/target/metric artifact hashes are unchanged.
Extension unit tests: 6 passed (half-life weights, future-event rejection, pseudo-count arithmetic, strong-preference preservation and cold-start fallback).

## 9. Reproduction and artifacts

Run from the project root:

```sh
.venv/bin/python scripts/prepare_validation.py
.venv/bin/python scripts/analyze_frequency_errors.py
.venv/bin/python scripts/evaluate_recency.py
.venv/bin/python scripts/evaluate_smoothing.py
.venv/bin/python scripts/test_frequency_extensions.py
.venv/bin/python scripts/verify_frequency_extensions.py
.venv/bin/python scripts/render_frequency_report.py
```

These steps assume the original comparison artifacts exist; recreate them with `scripts/compare_methods.py` and `scripts/verify_results.py` first if necessary.
Detailed artifacts: `personal_frequency_errors.json`, `personal_frequency_error_details.json`, `recency_*`, `smoothed_*`, `frequency_extension_tests.json` and `frequency_extension_verification.json`.
Original data sources and package disclosures are unchanged; see README.md and the original validation report. This analysis and implementation were AI-assisted in the recorded session.
