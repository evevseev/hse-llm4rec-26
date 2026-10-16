# Recall@10 and recommendation diagnosis

## Evaluation coverage

- Saved model macro Recall@10: **0.015682** (861 evaluable users). This recomputation matches the saved metric: true.
- Model hits: 94 out of 5142 relevant test items in the reported candidate set; micro Recall@10: 0.018281.
- Only 80/861 evaluable users have at least one hit; 781 have zero hits.
- Test users: 943; 82 have no relevant test film in the training movie pool; 13 distinct relevant test movie IDs are absent from train.
- There are 5155 relevant (rating >= 4) test ratings before candidate exclusions.
- Expected macro Recall@10 for a uniformly random 10-item list from the full catalog under the same user exclusions: 0.006336.

## Popularity baselines

- Popularity-ranked Top-10 over all catalog movies: macro Recall@10 **0.084741**, 433/5142 hits.
- Popularity-ranked Top-10 restricted to the 1611 movies in train: macro Recall@10 **0.084741**, 433/5142 hits.
- Both baselines use training rating counts (ties by training mean rating and movie ID), exclude each user's train/validation movies, and average per-user recall over the model's evaluable-user set.
- Separate fresh model run: current clip-before-Top-K ranking gave 0.010101; ranking by unclipped raw scores gave 0.008889 on the full catalog and 0.008889 on the train pool. 39.22% of Top-10 slots were capped at 5.0.

## User 1 recommendations and history

- User 1 has 244 train+validation ratings, mean rating 3.578, across 244 distinct films. Top genres by count: Drama (93, mean 3.91), Comedy (81, mean 3.42), Action (69, mean 3.41), Thriller (47, mean 3.57), Romance (39, mean 3.92).
- None of the displayed recommendations is in this user's train/validation history; 1 appears in their test history (test items are intentionally allowed by Top-K).

| Rank | Movie | Score | Genres | Train ratings | Popularity rank | User 1 test rating |
|---:|---|---:|---|---:|---:|---:|
| 1 | Close Shave, A (1995) | 5.0000 | Animation, Comedy, Thriller | 96 | 280 | — |
| 2 | Casablanca (1942) | 5.0000 | Drama, Romance, War | 222 | 61 | — |
| 3 | Pather Panchali (1955) | 5.0000 | Drama | 7 | 1087 | — |
| 4 | Santa with Muscles (1996) | 5.0000 | Comedy | 2 | 1390 | — |
| 5 | Lamerica (1994) | 4.9966 | Drama | 1 | 1488 | — |
| 6 | When We Were Kings (1996) | 4.9798 | Documentary | 34 | 614 | — |
| 7 | Wrong Trousers, The (1993) | 4.9417 | Animation, Comedy | 101 | 260 | 5 |
| 8 | My Man Godfrey (1936) | 4.9384 | Comedy | 20 | 787 | — |
| 9 | North by Northwest (1959) | 4.9228 | Comedy, Thriller | 151 | 146 | — |
| 10 | Manchurian Candidate, The (1962) | 4.9044 | Film-Noir, Thriller | 112 | 223 | — |

## Reading the result

- RMSE measures rating prediction on every held-out rating; Recall@10 measures whether a small ranked list recovers high-rated held-out films. They answer different questions, so lower RMSE does not guarantee high Recall@10.
- Recall here is macro-averaged over users, so a user with one relevant film has the same weight as a user with many. Most eligible users receive zero hits; a few users with multiple hits lift the mean.
- The saved model's Recall implementation ranks the full catalog, while the documented assignment asks to rank only training-pool movies. The popularity baselines quantify both candidate-pool variants; the model's strict train-pool reranking cannot be reconstructed from the saved output because factor weights were not serialized.
- Santa with Muscles and Lamerica are not necessarily errors: collaborative filtering ranks predicted compatibility, not general fame or quality. But these scores are weakly supported: Santa has two train ratings (both 5) and Lamerica one (5); the prediction is effectively extrapolating from tiny samples. Both fit a genre User 1 has rated, but their position is not reliable evidence of a strong preference.
- Clipping before Top-K creates many maximum-score ties. In the separate probe, raw-score ranking did not improve Recall; this is a diagnosable ranking weakness, not a demonstrated sole cause of the low score.
