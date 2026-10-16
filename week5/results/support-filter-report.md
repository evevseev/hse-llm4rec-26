# Minimum item-support experiment

- Seeds: 101, 202, 303; TensorFlow.js backend: wasm.
- Parameters per seed: factors=16, epochs=20, lr=0.01, reg=0.05, batchSize=64; checkpoint selected by validation RMSE.
- Training pool: 79619 ratings, 1611 distinct candidate movies; validation: 9596 ratings; test: 10785 ratings.
- N selected using validation only; metric is end-to-end macro Recall@10 over a fixed set of relevant validation targets (rating >= 4 with at least one train rating). Items filtered by N count as misses, avoiding artificial gains from shrinking the denominator.

## Validation, average over 3 seeds

| Minimum train ratings N | Macro Recall@10 (mean ± sample SD) | Micro Recall@10 (mean) | Hits (mean) | Users with relevant target after filter (mean) | Relevant targets filtered by N |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.013303 ± 0.001817 | 0.014521 | 67.0 | 846.0 | 0 |
| 5 | 0.017989 ± 0.002576 | 0.020445 | 94.3 | 843.0 | 66 |
| 10 | 0.022734 ± 0.002251 | 0.026152 | 120.7 | 840.0 | 168 |
| 20 | 0.029552 ± 0.001567 | 0.033232 | 153.3 | 834.0 | 392 |

Selected N: **20** (highest mean end-to-end macro Recall@10 on validation; ties prefer smaller N).

## Test, one post-selection evaluation phase

- Chosen N=20; per-seed macro Recall@10: 0.022688, 0.025997, 0.024746.
- Mean macro Recall@10: **0.024477 ± 0.001671** (sample SD); mean hits 152.0 of 5142 relevant targets.
- Exclusions: 13 unseen relevant movie IDs; 294 distinct relevant IDs below N; 82 users without a relevant train-seen test movie.

## Seed-averaged Top-10 lists after selected N

### User 1

| Rank | Movie | Mean score (3 seeds) | Train ratings |
|---:|---|---:|---:|
| 1 | Close Shave, A (1995) | 4.9149 | 96 |
| 2 | Wrong Trousers, The (1993) | 4.8843 | 101 |
| 3 | Casablanca (1942) | 4.8057 | 222 |
| 4 | Some Folks Call It a Sling Blade (1993) | 4.7240 | 34 |
| 5 | Schindler's List (1993) | 4.6760 | 257 |
| 6 | When We Were Kings (1996) | 4.6753 | 34 |
| 7 | Third Man, The (1949) | 4.6364 | 69 |
| 8 | Duck Soup (1933) | 4.6321 | 76 |
| 9 | Manchurian Candidate, The (1962) | 4.6300 | 112 |
| 10 | Lawrence of Arabia (1962) | 4.6204 | 155 |

### User 2

| Rank | Movie | Mean score (3 seeds) | Train ratings |
|---:|---|---:|---:|
| 1 | Casablanca (1942) | 4.7498 | 222 |
| 2 | Citizen Kane (1941) | 4.6204 | 175 |
| 3 | Big Sleep, The (1946) | 4.6153 | 62 |
| 4 | Manchurian Candidate, The (1962) | 4.6120 | 112 |
| 5 | Lawrence of Arabia (1962) | 4.6065 | 155 |
| 6 | Some Folks Call It a Sling Blade (1993) | 4.5974 | 34 |
| 7 | Silence of the Lambs, The (1991) | 4.5907 | 346 |
| 8 | Paths of Glory (1957) | 4.5540 | 28 |
| 9 | Amadeus (1984) | 4.5492 | 236 |
| 10 | When We Were Kings (1996) | 4.5431 | 34 |

Per-user validation comparisons for all eligible users are in `support-filter-validation-users.csv`.

Caveat: the test labels were withheld in this script until N was chosen, but the existing test split had been inspected in an earlier analysis, so this is not a historically untouched holdout.
