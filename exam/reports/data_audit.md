# SWEET.TV initial data audit

Audit date: 2026-10-25. The official Kaggle archive was downloaded and extracted.
This document records the initial audit before modelling; subsequent experiments
are documented separately. All counts are full-file measurements, not estimates.

## Actual files

| File | Bytes | Data rows | Labelled airings | Distinct nonzero IDs |
|---|---:|---:|---:|---:|
| dataset11-30.csv | 396,216,555 | 5,821,987 | — | — |
| export_arh_11-20-final.csv | 153,322,643 | 1,074,235 | 115,613 | 5,847 |
| export_arh_21-30-final.csv | 154,366,907 | 1,074,394 | 121,505 | 6,363 |
| export_arh_31-42-final.csv | 185,952,991 | 1,295,378 | 144,774 | 6,636 |
| submission.csv | 38,348 | 1,260 | — | — |

Template users are unique and each original row has five zeros. SHA-256 values
are saved in `audit_results.json`. The assignment's item counts include zero;
the numbers of recommendable IDs are one smaller.

The log contains 4,914 users and 202 channels. The schedules contain 400, 403,
and 404 channels respectively. Log timestamps range from 2020-03-09 00:00:02
to 2020-07-26 23:59:58, covering ISO weeks 11–30. The test schedule starts on
2020-07-27. Some airings extend across file boundaries, so temporal splits must
use explicit timestamps rather than filenames alone.

## Schema and data quality

The log columns are `user_id,vsetv_id,start_time,stop_time,duraton`.
Schedule timestamps use `DD.MM.YYYY HH:MM:SS`, whereas log timestamps use
`YYYY-MM-DD HH:MM:SS`. User IDs are preserved as strings because some exceed
signed int64 and floating-point conversion would lose precision.

- The first schedule has 958,622 zero-ID rows: only about 10.76% of its rows
  have a label. This is a fraction of rows, not a measured fraction of airtime seconds.
- Among labelled rows in that file, category is always present. Genre fields
  1/2/3 are missing in 5,375 / 47,084 / 95,437 rows; director in 15,428; actors
  in 15,239. These are airing-row counts, not distinct-item counts.
- One row has zero duration and cannot be used as a denominator; its source
  record is preserved in the JSON.
- The two training schedules have no duplicate labelled airing keys
  `(channel_id,start_time,end_time,tv_show_id)` and no overlapping labelled
  airings within a channel under the initial naive-time interpretation.
  Unlabelled-airing overlaps were not checked.
- There are 8,234 nonzero IDs across both training schedules; 1,437 of the
  6,636 test-schedule IDs are absent from that union.

Reported viewing-duration quantiles in seconds: min=61, Q25=133, median=396,
Q75=1,452, Q90=3,911, Q99=14,079, max=342,145. Long channel sessions can span
many airings and must not be attributed to a single programme.

## Daylight-saving-time diagnostic

In 117 rows, `duraton` is 3,600 seconds smaller than naive `stop_time-start_time`.
All 117 differences disappear when interpreting timestamps as `Europe/Kyiv`
with Python zoneinfo. This supports a DST explanation, but the CSV has no
explicit timezone annotation.

For example, log line 1,250,165 spans 2020-03-28 22:47:45 to
2020-03-30 09:02:48: naive elapsed time is 123,303 seconds; the supplied duration
and Kyiv-aware elapsed time are both 119,703 seconds.

The initial audit's global join counts below deliberately use naive timestamps;
they are diagnostics, not final training labels. The March 9 examples do not
cross the DST transition. A modelling pipeline must explicitly define timezone
handling for both logs and schedule durations.

## Actual interval-join examples

Intervals are half-open `[start,end)`, channel IDs must agree, and overlap must
be positive. A watched airing requires overlap / airing duration >=0.8.
Zero-ID airings never become recommendable items.

User `7981779138282146703` watched channel `1495` (NickToons) on March 9 from
00:40:50 to 02:28:55, a 6,485-second session: `dataset11-30.csv`, line 1517.
The labelled matches in `export_arh_11-20-final.csv` are:

| Schedule line | Programme ID | Original title | Airing | Overlap | Fraction | Qualified |
|---:|---:|---|---|---:|---:|---|
| 1062940 | 12001732 | Пингвины из «Мадагаскара» | 01:16–01:39 | 1,380 s | 100% | Yes |
| 1062942 | 12002856 | Элвиннн!!! и бурундуки | 02:01–02:12 | 660 s | 100% | Yes |
| 1062943 | 12002856 | Элвиннн!!! и бурундуки | 02:12–02:24 | 720 s | 100% | Yes |
| 1062944 | 12001682 | Губка Боб Квадратные Штаны | 02:24–02:47 | 295 s | 21.38% | No |

The last airing overlaps only until 02:28:55: 295 / 1,380 seconds. A long session
does not imply a full watch of every programme. The repeated ID 12002856 is one
item with two separately qualified airings. Gaps in this labelled-only table
must not be interpreted as absence of broadcast content.

User `15166841293414410417` watched channel `945` (Трофей) from 00:02:58 to
00:06:41 on March 9: log line 105. Schedule line 754442 contains
`Календарь рыболова.`, category `Познавательное`, airing 00:02–00:09, ID zero.
Overlap is 223 / 420 seconds (53.10%); the missing ID excludes it as an item.
This also demonstrates that zero does not reliably mean “film”.

## Initial join diagnostics

All 5,821,987 log rows and 237,118 labelled training-schedule airings were
processed. No test-period viewing behaviour is available or used.

- 2,964,346 log rows touch at least one labelled airing.
- There are 3,847,696 log-row/labelled-airing overlap pairs.
- 570,588 pairs meet the 80% threshold, from 337,779 log rows.
- All template users occur in the log; two have no labelled overlap; five have
  no individually qualified pair.

These are pair-level statistics, not merged user-airing labels. Fragments have
not been combined, repeated logs have not been deduplicated, and the global
join has not applied DST correction. Cold-start counts may change after merging.
Counts concern all weeks 11–30, not only the future validation training window.

For the two saved sessions, indexed matching was independently checked against
a full linear scan of that channel's labelled airings. Both matched exactly
(zero and four matches). This verifies the examples, not every possible lookup.

## Reproduction and artifacts

Run `python3 scripts/audit_data.py` from the project root with the CSV files in
`data/`. Dependencies: Python standard library and the system timezone database.
The recorded run used Python 3.12.11 on macOS arm64, took 27.071 seconds and
peaked at 198,574,080 bytes RSS (about 189.4 MiB). Runtime includes hashing,
reading, statistics and matching, but not downloading. No randomness is used.

- `audit_results.json`: schemas, hashes, measurements, anomalies and environment.
- `join_examples.csv`: source lines, IDs, intervals, overlaps and watch fractions.
- `kaggle_description_notes.md`: source quotations and unresolved details.

Original programme titles/categories are preserved as source data. Documentation,
code comments, column names and generated explanatory text are in English.
No external model or third-party implementation was used for this initial audit.
