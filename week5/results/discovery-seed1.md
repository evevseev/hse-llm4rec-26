# Familiar tastes vs. new movie discovery

- Seed 1, TensorFlow.js wasm, 16 factors, 20 epochs, lr=0.01, reg=0.05, batchSize=64; selected epoch 3 by validation RMSE 1.007781.
- Candidate filter: at least 20 train ratings. Lists are averaged from one deterministic seed only; the model excludes movies already rated in train or validation.
- Familiar title means the user rated that exact movie in train or validation. Familiar genre means the genre occurs in at least one such past rating. A favored genre is more conservatively defined as at least five past genre-tagged ratings with mean >=4.0.
- This is an offline comparison against historical genres, not evidence that the user personally knows every unviewed catalog title. No test labels or ratings are used.

## User 1

Past history: 244 ratings on 244 distinct movies; mean score 3.578. Most-seen genres: Drama (93 ratings, mean 3.91), Comedy (81 ratings, mean 3.42), Action (69 ratings, mean 3.41), Thriller (47 ratings, mean 3.57), Romance (39 ratings, mean 3.92), Adventure (38 ratings, mean 2.92), Sci-Fi (37 ratings, mean 3.95), War (24 ratings, mean 3.75).
Favorite-genre rule: at least 5 genre-tagged past ratings and mean rating >= 4.0. Genres selected: none.
Top-10: 10/10 unseen titles; 10 overlap a previously rated genre; 0 overlap a favored genre; 0 have only genres absent from history.

| # | Movie | Score | Train ratings | Genres | Familiar genres | Favored genres |
|---:|---|---:|---:|---|---|---|
| 1 | 8 1/2 (1963) | 4.9904 | 29 | Drama | Drama | — |
| 2 | Wings of Desire (1987) | 4.8865 | 44 | Comedy, Drama, Romance | Comedy, Drama, Romance | — |
| 3 | Wrong Trousers, The (1993) | 4.8577 | 101 | Animation, Comedy | Animation, Comedy | — |
| 4 | Third Man, The (1949) | 4.8016 | 69 | Mystery, Thriller | Mystery, Thriller | — |
| 5 | 12 Angry Men (1957) | 4.6523 | 108 | Drama | Drama | — |
| 6 | East of Eden (1955) | 4.6482 | 54 | Drama | Drama | — |
| 7 | Dr. Strangelove or: How I Learned to Stop Worrying and Love the Bomb (1963) | 4.6189 | 170 | Sci-Fi, War | Sci-Fi, War | — |
| 8 | Manchurian Candidate, The (1962) | 4.6064 | 112 | Film-Noir, Thriller | Film-Noir, Thriller | — |
| 9 | Big Sleep, The (1946) | 4.5997 | 62 | Film-Noir, Mystery | Film-Noir, Mystery | — |
| 10 | Great Escape, The (1963) | 4.5995 | 105 | Adventure, War | Adventure, War | — |

## User 2

Past history: 55 ratings on 55 distinct movies; mean score 3.818. Most-seen genres: Drama (32 ratings, mean 3.84), Romance (16 ratings, mean 4.13), Comedy (15 ratings, mean 3.73), Thriller (11 ratings, mean 3.64), Action (8 ratings, mean 4.25), Crime (8 ratings, mean 4.13), Sci-Fi (4 ratings, mean 3.75), Mystery (4 ratings, mean 3.50).
Favorite-genre rule: at least 5 genre-tagged past ratings and mean rating >= 4.0. Genres selected: Romance, Crime, Action.
Top-10: 10/10 unseen titles; 9 overlap a previously rated genre; 4 overlap a favored genre; 1 have only genres absent from history.

| # | Movie | Score | Train ratings | Genres | Familiar genres | Favored genres |
|---:|---|---:|---:|---|---|---|
| 1 | Godfather: Part II, The (1974) | 4.8115 | 182 | Action, Crime, Drama | Action, Crime, Drama | Action, Crime |
| 2 | Old Man and the Sea, The (1958) | 4.8093 | 25 | Adventure, Drama | Adventure, Drama | — |
| 3 | Paris Is Burning (1990) | 4.7732 | 27 | Documentary | — | — |
| 4 | Close Shave, A (1995) | 4.7283 | 96 | Animation, Comedy, Thriller | Animation, Comedy, Thriller | — |
| 5 | Amadeus (1984) | 4.7048 | 236 | Drama, Mystery | Drama, Mystery | — |
| 6 | Apocalypse Now (1979) | 4.6762 | 201 | Drama, War | Drama, War | — |
| 7 | Casablanca (1942) | 4.6700 | 222 | Drama, Romance, War | Drama, Romance, War | Romance |
| 8 | Philadelphia Story, The (1940) | 4.6605 | 85 | Comedy, Romance | Comedy, Romance | Romance |
| 9 | M (1931) | 4.6506 | 39 | Crime, Film-Noir, Thriller | Crime, Film-Noir, Thriller | Crime |
| 10 | Manchurian Candidate, The (1962) | 4.6241 | 112 | Film-Noir, Thriller | Film-Noir, Thriller | — |

## Product interpretation

Because Top-10 excludes exact titles in train and validation, 10/10 recommendations are new titles by construction. The discovery question is therefore whether those new titles remain connected to genres the user has rated well, and whether any introduce entirely unseen genres.
A list dominated by high-rated familiar genres can offer low-risk discovery: unfamiliar titles with a recognizable taste rationale. Recommendations with no genre overlap are more exploratory and carry more relevance risk. The service can use both kinds to balance engagement with discovery; the score and observed genre history provide a simple explanation for each choice.
