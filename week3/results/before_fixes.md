# Baseline before hardening

The starter in `original/` had TODOs for the rating matrix, cosine similarity, and both CF recommenders, so it could not produce a working CF Top-5 as supplied. For a numerical baseline, this report reconstructs the intended executable version: co-rated-only cosine, no overlap shrinkage, one supporting neighbor/co-rater is enough, and no title-alias guard.

## Dataset and original data issues

- 943 users, 1682 movies, 100,000 ratings; 6.30% of matrix cells are rated.
- The u.item file is ISO-8859-1, but the starter read it as UTF-8 response text. Movie ID 543 was decoded as “Mis�rables, Les (1995)” instead of “Misérables, Les (1995)”.
- The genre parser started at the “unknown” flag, shifting every named genre by one position.
- There are 18 groups of identical movie titles under different IDs. In 655 user/title cases, one ID was rated while another ID for the same title remained unrated.

## Reconstructed unfiltered CF baseline

- With raw co-rated-only cosine, 942/943 users had every displayed User-Based Top-5 score equal to 5.000.
- For 751/943 users, a majority of the selected top-20 neighbors shared at most two movies.
- Before title-alias filtering, the raw baseline produced 2 User-Based and 0 Item-Based Top-5 entries whose title matched a movie already rated by that user under another ID.

These duplicate counts are recommendation rows, not distinct users. “Before” refers to this reconstructed executable algorithm, not to the literal TODO functions in `original/`.
