# Week 2: Movie Recommender

## What was wrong in the starter code

The `u.item` parser treated the `unknown` flag as the first real genre. That shifted every genre label by one and dropped Western. Also, `u.item` is ISO-8859-1 encoded, but `fetch().text()` decodes as UTF-8, producing replacement characters in titles such as `Misérables, Les`. The original recommender used Jaccard similarity for just one selected movie.

## What changed in `fixed/`

- Genre parsing now skips `unknown` and reads the 18 actual genre flags.
- Movie titles are decoded from ISO-8859-1 before parsing, preserving accented characters.
- The app accepts one to three liked movies and builds a profile by averaging their genre vectors.
- Recommendations use cosine similarity and show the Top-5, excluding selected movies and duplicate titles.
- Equal cosine scores are broken by the number of unique raters, then title and ID. This is deterministic and favors popular movies in ties, so it can reduce exposure for lesser-known films.

## Run the app

From this directory, start a local static server:

```bash
python3 -m http.server 8000 --directory fixed
```

Open <http://localhost:8000> in a browser. Serving the files over HTTP is needed for the app to fetch `u.item` and `u.data`.

## Run the checks

Run these commands from this directory:

```bash
node eval/compare-recommendations.js
node eval/verify-cosine-recommendations.js
node eval/analyze-recommendations.js
```

The first checks the genre parser and compares the old Jaccard results with `fixed/`. The second verifies a cosine score by hand, checks duplicate handling, and checks accented-title decoding. The analysis script compares item-to-item and profile recommendations, then writes `results/recommendation-analysis.md`.
