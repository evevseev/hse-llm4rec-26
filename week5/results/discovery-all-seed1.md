# Recommendation discovery and repetition — all users, seed 1

- Model checkpoint: epoch 3, validation RMSE 1.007781; candidate minimum N=20; testSet was kept empty and not accessed.
- Genuine genre discovery is a Top-10 movie with at least one genre absent from the user's train+validation history. An obvious choice is defined as all genres familiar and the movie in the most-popular 10% of train items. Popularity novelty is reported separately as mean self-information.

## Main all-user measures

- **Mean per-user new-genre share (primary): 9.36%**; users with at least one such item: 440/943.
- Across 9430 recommendation slots: 883 have a new-to-user genre (9.36%); 8547 use only familiar genres.
- Obvious choices by the operational definition: 2011/9430 (21.33%). Any Top-10 item in the train popularity top decile: 2140/9430.
- Mean popularity self-information: 10.223 bits per slot.
- Catalog diversity: 623 distinct movies surfaced from 809 eligible movies (77.01% coverage); mean pairwise Top-10 Jaccard 0.0312, mean shared titles 0.558 of 10.
- Exact previously rated title repeats: 0/9430 (they are excluded by construction).

## User 1

Past ratings: 244; mean 3.578; known genres: 18. Preferred genres (>=5 past genre ratings and mean >=4): none.
New-to-user genres in Top-10: 0/10; exact past-title repeats: 0.
Top historic genres: Drama (93, mean 3.91), Comedy (81, mean 3.42), Action (69, mean 3.41), Thriller (47, mean 3.57), Romance (39, mean 3.92).

| # | Movie | Score | Genres | Familiar genres | New genres | Train ratings | Train popularity rank |
|---:|---|---:|---|---|---|---:|---:|
| 1 | 8 1/2 (1963) | 4.9904 | Drama | Drama | — | 29 | 687 |
| 2 | Wings of Desire (1987) | 4.8865 | Comedy, Drama, Romance | Comedy, Drama, Romance | — | 44 | 531 |
| 3 | Wrong Trousers, The (1993) | 4.8577 | Animation, Comedy | Animation, Comedy | — | 101 | 260 |
| 4 | Third Man, The (1949) | 4.8016 | Mystery, Thriller | Mystery, Thriller | — | 69 | 375 |
| 5 | 12 Angry Men (1957) | 4.6523 | Drama | Drama | — | 108 | 239 |
| 6 | East of Eden (1955) | 4.6482 | Drama | Drama | — | 54 | 465 |
| 7 | Dr. Strangelove or: How I Learned to Stop Worrying and Love the Bomb (1963) | 4.6189 | Sci-Fi, War | Sci-Fi, War | — | 170 | 116 |
| 8 | Manchurian Candidate, The (1962) | 4.6064 | Film-Noir, Thriller | Film-Noir, Thriller | — | 112 | 229 |
| 9 | Big Sleep, The (1946) | 4.5997 | Film-Noir, Mystery | Film-Noir, Mystery | — | 62 | 408 |
| 10 | Great Escape, The (1963) | 4.5995 | Adventure, War | Adventure, War | — | 105 | 250 |

## User 2

Past ratings: 55; mean 3.818; known genres: 14. Preferred genres (>=5 past genre ratings and mean >=4): Romance, Crime, Action.
New-to-user genres in Top-10: 1/10; exact past-title repeats: 0.
Top historic genres: Drama (32, mean 3.84), Romance (16, mean 4.13), Comedy (15, mean 3.73), Thriller (11, mean 3.64), Action (8, mean 4.25).

| # | Movie | Score | Genres | Familiar genres | New genres | Train ratings | Train popularity rank |
|---:|---|---:|---|---|---|---:|---:|
| 1 | Godfather: Part II, The (1974) | 4.8115 | Action, Crime, Drama | Action, Crime, Drama | — | 182 | 101 |
| 2 | Old Man and the Sea, The (1958) | 4.8093 | Adventure, Drama | Adventure, Drama | — | 25 | 741 |
| 3 | Paris Is Burning (1990) | 4.7732 | Documentary | — | Documentary | 27 | 709 |
| 4 | Close Shave, A (1995) | 4.7283 | Animation, Comedy, Thriller | Animation, Comedy, Thriller | — | 96 | 283 |
| 5 | Amadeus (1984) | 4.7048 | Drama, Mystery | Drama, Mystery | — | 236 | 52 |
| 6 | Apocalypse Now (1979) | 4.6762 | Drama, War | Drama, War | — | 201 | 81 |
| 7 | Casablanca (1942) | 4.6700 | Drama, Romance, War | Drama, Romance, War | — | 222 | 62 |
| 8 | Philadelphia Story, The (1940) | 4.6605 | Comedy, Romance | Comedy, Romance | — | 85 | 308 |
| 9 | M (1931) | 4.6506 | Crime, Film-Noir, Thriller | Crime, Film-Noir, Thriller | — | 39 | 570 |
| 10 | Manchurian Candidate, The (1962) | 4.6241 | Film-Noir, Thriller | Film-Noir, Thriller | — | 112 | 229 |

## Interpretation for a streaming service

For discovery, the primary measure says 9.36% of the average user's Top-10 introduces a genre not seen in their history. Most recommendations therefore broaden the catalog within known taste areas rather than expand genre interests. The low list Jaccard/unique-title coverage indicate different users are not receiving an identical list; the separate popularity/self-information metric shows whether those different titles are mainstream or niche.

All-user table with per-user genre novelty is in `discovery-all-seed1.json`; no test ratings were used.
