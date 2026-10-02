# Analytics

## User-Based vs Item-Based: quality and speed

Neither method is universally more accurate. Compare quality offline by hiding known ratings and measuring Recall@5/NDCG@5. User-Based finds similar people; Item-Based finds co-rated films and can precompute/cache film similarities. Item-Based often scales better when there are many more users than items; User-Based can be cheaper when items outnumber users.

This dataset has 943 users and 1682 movies. A dense full-pair build is approximately 444,153 user pairs × 1682 movies = 747,065,346 coordinates for User-Based, versus 1,413,721 movie pairs × 943 users = 1,333,138,903 for Item-Based (1.78× more).

For one query in this implementation, user 1 has 272 ratings: User-Based scans about 1,585,386 vector positions; on-the-fly Item-Based scans about 361,659,360 (228.1×). Precomputing the item matrix trades preprocessing/storage for faster requests. These are operation estimates, not measured wall-clock times.

## Missing-value strategies

| Strategy | Hand-calculated similarity | Simplicity, bias, and cost |
|---|---:|---|
| Ignore missing values; compare co-rated entries | 1.000 | Simplest and does not invent ratings; one shared positive rating can falsely look perfect. Sparse intersections are cheap. |
| Fill missing values with user means | 0.886 | Dense vectors, but imputed values can create artificial agreement/disagreement and bias results toward averages. |
| Weight by overlap count; threshold 5 | 0.200 for one shared rating | Adds a small overlap-count/weight step and suppresses weak evidence; threshold tuning may disadvantage sparse users/items. |

Example: A=(5,1,missing), B=(5,missing,1). Co-rated-only compares [5] with [5], cosine 1. Row-mean imputation gives A=(5,1,3), B=(5,3,1): dot=31, squared norms=35 each, cosine=31/35≈0.886. Overlap weighting scales the one-common-item cosine by 1/5=0.2. Mean imputation requires a choice of user/item mean and may create relationships absent from the data.

## Cold start and sparsity

The matrix has 1,586,126 possible cells and 100,000 observed ratings (6.30% density). New users have no history for neighbors or an item profile; new movies have no co-ratings. Use content/genre recommendations or onboarding until interactions arrive.

Across all 444,153 unordered pairs of distinct users, median shared films = **10**; pairs sharing at most two films = **63,490 (14.29%)**. Median 10 checks out; “about 13%” is somewhat below the measured 14.29%. 15,043 pairs have no shared ratings. Cosine on one common positive rating is always 1, so small overlap is weak evidence.

## Same-user Top-5: genre-based vs CF

Week 2 asks for up to three liked movies, not a user ID. For a reproducible same-user comparison, I selected user 1’s three highest-rated movies (ties by title, then ID): 12 Angry Men (1957) (5); Alien (1979) (5); Aliens (1986) (5). CF uses all of user 1’s ratings.

| Rank | Genre-based (genre cosine) | User-Based CF (predicted rating) | Item-Based CF (predicted rating) |
|---:|---|---|---|
| 1 | Alien 3 (1992) (0.904) | Trainspotting (1996) (5.000) | A Chef in Love (1996) (4.068) |
| 2 | Terminator, The (1984) (0.894) | Casablanca (1942) (5.000) | Rendezvous in Paris (Rendez-vous de Paris, Les) (1995) (4.047) |
| 3 | Terminator 2: Judgment Day (1991) (0.894) | Chinatown (1974) (5.000) | Last Summer in the Hamptons (1995) (4.041) |
| 4 | Face/Off (1997) (0.894) | Schindler's List (1993) (4.800) | Bitter Sugar (Azucar Amargo) (1996) (4.038) |
| 5 | Arrival, The (1996) (0.894) | L.A. Confidential (1997) (4.601) | Wonderful, Horrible Life of Leni Riefenstahl, The (1993) (4.029) |

Genre-based recommendations match the selected films’ metadata. CF follows audience rating patterns, so it can cross genre boundaries. Scores have different meanings and are not directly comparable; a single user’s list does not establish which method has better quality.
