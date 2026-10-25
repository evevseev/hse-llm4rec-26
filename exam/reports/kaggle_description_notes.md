# Kaggle description cross-check

Retrieved on 2026-10-25 through the Kaggle API tools for competition
`sweettv-tv-program-recommender`. This is a source summary, not a complete page export.

- Data: https://www.kaggle.com/competitions/sweettv-tv-program-recommender/data
- Evaluation: https://www.kaggle.com/competitions/sweettv-tv-program-recommender/overview/evaluation
- Description: https://www.kaggle.com/competitions/sweettv-tv-program-recommender/overview/description

## Verbatim excerpts from data-description

> **vsetv_id** is the same as **channel_id** in export_arh_*.csv files.

> all entries with tv_show_id = 0 were removed from TV program schedule files

> for each user and each TV show user screen time (time user watched the show divided by total duration of the show) was calculated. Only TV shows with high screen time (>= 0.8) were taken into account.

> for each user high-screen time TV shows frequency was calculated

> for each user **strictly** 5 most frequent TV shows were selected DESC (#1 is the most frequent, #5 is the least frequent amongst top 5) - order matters!

> Private/public test data is split BY USERS (50/50) - not by time.

## Metric and file format

Evaluation explicitly specifies `Mean Average Precision @ 5 (MAP@5)`.
The header is `user_id,tv_show_id`; the second column contains five space-separated
IDs. Description specifies the subsequent twelve weeks, 31–42.

## Discrepancies and unresolved details

- The page lists obsolete filenames: `dataset11-30week.csv`, `export_arh_10-19.csv`,
  `export_arh_20-30.csv`, `export_arh_31-42.csv`. The archive instead contains
  `dataset11-30.csv`, `export_arh_11-20-final.csv`, `export_arh_21-30-final.csv`,
  `export_arh_31-42-final.csv`, and `submission.csv`, matching task.md.
- The documented log columns `end_time`, `duration` are actually `stop_time`, `duraton`.
- One passage says `sorted ASC`, but explains that the most frequent item comes
  first; the answer-construction procedure explicitly says `DESC`.
- The phrase “int stands for a TV show episode and 0 for films” is not a reliable
  semantic description of zero. A real zero-ID example is a fishing calendar in
  the educational category. Zero is excluded as unlabelled airtime.
- The pages do not specify fragment merging, duplicate handling, tie-breaking,
  timezone, or the exact hidden-label implementation. Counting qualified airings
  after applying an 80% threshold is a documented working reconstruction.
- Standard MAP@5 uses membership in the relevant set and prediction ranks, not
  exact agreement with target ranks. The hidden scoring implementation was not run.
