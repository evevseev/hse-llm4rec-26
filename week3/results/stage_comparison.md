# Stage comparison

The first three rows use the same user-neighbor definition (top 20 positive similarities) and differ by overlap weighting and minimum recommendation support. The final alias guard changes candidate eligibility/deduplication only.

| User-Based stage | All Top-5 scores 5.000 | Majority of neighbors overlap ≤2 | Empty lists | Duplicate-rated title rows |
|---|---:|---:|---:|---:|
| Raw co-rated cosine; one supporter | 942/943 (99.89%) | 751/943 (79.64%) | 0 | 2 |
| Overlap-weighted cosine (5); one supporter | 943/943 (100.00%) | 0/943 (0.00%) | 0 | 4 |
| Overlap-weighted cosine (5); 3 User-Based supporters | 145/943 (15.38%) | 0/943 (0.00%) | 0 | 2 |

## Duplicate-title recommendations across all users

The “before title guard” counts use the current overlap and support settings: overlap threshold 5, at least 3 neighbors for User-Based, and at least 3 distinct co-raters for Item-Based. The after run uses the same settings plus title-alias exclusion and title deduplication.

| CF method | Before: duplicate-rated title rows | Users affected | After |
|---|---:|---:|---:|
| User-Based | 2 | 2 | 0 |
| Item-Based | 0 | 0 | 0 |

## Item-Based support filter

The candidate now needs 3 distinct users who rated it and at least one film from the active user’s history. The rule is applied before Top-5 selection. Under the final rule, empty Item-Based Top-5 lists: 0/943; lists shorter than five: 0/943.

### Item-Based Top-5 examples before/after the support filter

| User | Minimum support 1 | Minimum support 3 |
|---:|---|---|
| 1 | Cyclo (1995) (4.378); Entertaining Angels: The Dorothy Day Story (1996) (4.375); Office Killer (1997) (4.279); King of New York (1990) (4.222); Little City (1998) (4.198) | A Chef in Love (1996) (4.068); Rendezvous in Paris (Rendez-vous de Paris, Les) (1995) (4.047); Last Summer in the Hamptons (1995) (4.041); Bitter Sugar (Azucar Amargo) (1996) (4.038); Wonderful, Horrible Life of Leni Riefenstahl, The (1993) (4.029) |
| 196 | Very Natural Thing, A (1974) (4.500); Walk in the Sun, A (1945) (4.500); Sunchaser, The (1996) (4.250); War at Home, The (1996) (4.250); Death in Brunswick (1991) (4.091) | Stonewall (1995) (3.904); Innocents, The (1961) (3.894); Wonderful, Horrible Life of Leni Riefenstahl, The (1993) (3.892); Aparajito (1956) (3.889); The Innocent (1994) (3.885) |

User-Based list lengths after the final support rule (0 through 5): 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 943.
