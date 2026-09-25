# MovieLens 100K Recommendation Analysis

Generated from the data in `fixed/` by running `node eval/analyze-recommendations.js`.

## How to read the metrics

- **Item-to-item and profile** use the same cosine metric and tie-break rule. The single-item example is Toy Story; the example profile contains Toy Story, Star Wars, and Fargo.
- To test normalization, cosine is compared with the **raw dot product** on identical queries. For binary item-to-item vectors: `cosine = shared genres / (√query genres × √candidate genres)`; the dot product simply counts shared genres. For one query, its vector length is fixed while a candidate's vector length grows with its number of genres.
- “Multi-genre” means at least 5 genres. “Popular” means the catalog's top 20% by unique raters.
- “Long tail” means movies with no more unique raters than the catalog's lower-quartile threshold (**7**); this is 458 of 1664 movies (27.5%). Ties at the threshold can make the share slightly greater than 25%.
- The genre table groups movies by genre count; average raters are unique users averaged across unique movie titles.
- Long-tail share is measured across **Top-5 recommendation slots**: if a movie appears for multiple queries, it counts once per slot. The last column also shows the number of unique recommended Long-tail titles.
- Dot product is an analysis baseline, not another option in the app.
- Main comparisons break ties by unique rater count, then title and ID. The separate Long-tail test uses ascending ID to isolate the tie-break effect.

## Top-5: one movie and a three-movie profile

Single movie: **Toy Story (1995)**. Profile: **Toy Story (1995), Star Wars (1977), Fargo (1996)**. Shared titles between the Top-5 lists: **0 of 5**.

### Item-to-item: Toy Story

| # | Movie | Cosine | Genres | Unique raters | Long tail? |
|---:|---|---:|---:|---:|:---:|
| 1 | Aladdin and the King of Thieves (1996) | 1.000000 | 3 | 26 | no |
| 2 | Aladdin (1992) | 0.866025 | 4 | 219 | no |
| 3 | Goofy Movie, A (1995) | 0.866025 | 4 | 20 | no |
| 4 | George of the Jungle (1997) | 0.816497 | 2 | 162 | no |
| 5 | Beavis and Butt-head Do America (1996) | 0.816497 | 2 | 156 | no |

### Profile: Toy Story + Star Wars + Fargo

| # | Movie | Cosine | Genres | Unique raters | Long tail? |
|---:|---|---:|---:|---:|:---:|
| 1 | Empire Strikes Back, The (1980) | 0.738549 | 6 | 367 | no |
| 2 | Transformers: The Movie, The (1986) | 0.738549 | 6 | 32 | no |
| 3 | Return of the Jedi (1983) | 0.674200 | 5 | 507 | no |
| 4 | Kid in King Arthur's Court, A (1995) | 0.615457 | 6 | 22 | no |
| 5 | Princess Bride, The (1987) | 0.603023 | 4 | 324 | no |

## Genre count and catalog popularity

Each movie is counted once after duplicate titles are merged. Average raters is the mean number of unique raters per movie in each group.

| Genres per movie | Movies | Mean unique raters per movie |
|---:|---:|---:|
| 0 | 2 | 5.0 |
| 1 | 822 | 36.5 |
| 2 | 563 | 68.8 |
| 3 | 212 | 103.3 |
| 4 | 51 | 134.0 |
| 5 | 11 | 162.5 |
| 6 | 3 | 140.3 |

## Does cosine normalization reduce the advantage of broad-genre movies?

The catalog-wide comparison uses all movies with at least one genre as item-to-item queries. We also use real users with at least three distinct movies rated 4 or 5: item-to-item uses their highest-rated movie, while the profile uses those same three movies. Each query returns a Top-5.

| Query set and ranking | Queries | Recommendation slots | Mean genres | With 5+ genres | Mean unique raters | Long-tail slots | Multi-genre popular* | Unique titles / Long tail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| All item-to-item queries — cosine | 1662 | 8310 | 1.70 | 0.4% | 204.1 | 1.8% | 0.2% | 548 / 50 |
| All item-to-item queries — dot product | 1662 | 8310 | 2.99 | 9.1% | 331.8 | 0.4% | 7.1% | 285 / 16 |
| Users: one movie — cosine | 942 | 4710 | 2.21 | 2.1% | 208.0 | 1.0% | 1.3% | 325 / 8 |
| Users: one movie — dot product | 942 | 4710 | 3.26 | 11.4% | 294.8 | 0.3% | 7.7% | 194 / 4 |
| Users: three-movie profile — cosine | 942 | 4710 | 2.74 | 4.6% | 196.7 | 2.0% | 2.6% | 384 / 21 |
| Users: three-movie profile — dot product | 942 | 4710 | 3.91 | 25.2% | 219.7 | 0.9% | 15.1% | 214 / 12 |

* Recommendations with both 5+ genres and popularity in the catalog's top 20%.

Cosine does not exclude movies with many genres: with the same number of shared genres, a broader candidate has a larger denominator and a lower score. This normalizes genre-vector length, not popularity. The “multi-genre popular” column shows whether the combined share of broad-genre blockbusters changes. Popularity is not part of the cosine score, but the app uses it to break equal-score ties.

**Finding:** Across all single-item queries, cosine recommended films with an average of 1.70 genres versus 2.99 for dot product. Films with 5+ genres made up 0.4% versus 9.1%; multi-genre popular films made up 0.2% versus 7.1%. The same pattern appears for real-user profiles (2.74 versus 3.91 genres; 2.6% versus 15.1% multi-genre popular films). On this dataset, cosine normalization reduces the advantage of movies with many genres; popularity itself is not normalized by cosine.

## Which approach surfaces more Long-tail movies?

Item-to-item and profile results use the same user queries and cosine metric. Compare “Long-tail slots” and “Unique titles / Long tail” for **“Users: one movie — cosine”** and **“Users: three-movie profile — cosine.”** More Long-tail slots means more frequent exposure; more unique Long-tail titles means a wider selection of lesser-known movies.

**Finding:** Across 942 paired user queries, three-movie profiles returned Long-tail films in 2.0% of recommendation slots versus 1.0% for item-to-item. They covered 21 unique Long-tail films versus 8. In this sample, profiles surfaced more and a wider range of lesser-known films, although the absolute shares remained low. The popularity tie-break works the same way for both approaches and favors better-known movies when cosine scores tie.

## How much does the popularity tie-break change Long-tail exposure?

The same user queries and cosine scores are used in both cases. Only the order of equal-scoring movies changes, keeping Top-5 and deduplication fixed to isolate the tie-break effect.

The comparison is between the current popularity rule and ascending ID (the original `u.item` row order).

| Query type | Tie-break for equal scores | Long-tail slots / total slots | Long-tail share | Unique Long-tail movies |
|---|---|---:|---:|---:|
| Item-to-item: one movie | Popularity | 49/4710 | 1.0% | 8 |
| Item-to-item: one movie | Ascending ID | 102/4710 | 2.2% | 13 |
| Profile: three movies | Popularity | 96/4710 | 2.0% | 21 |
| Profile: three movies | Ascending ID | 197/4710 | 4.2% | 24 |

**Tie-break effect:** On the same 942 queries, sorting tied scores by ascending ID gives 102/4710 Long-tail slots (2.2%) for item-to-item and 197/4710 (4.2%) for profiles. The current popularity rule changes these to 49/4710 (1.0%) and 96/4710 (2.0%). Compared with the ID tie-break, the popularity rule reduces Long-tail slots for item-to-item by 53 and reduces Long-tail slots for profiles by 101. This isolates the tie-break effect while keeping cosine, Top-5, and deduplication unchanged.
