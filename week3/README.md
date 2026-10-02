# Week 3 — Collaborative Filtering

## What was wrong in the starter

The code in `original/` left the rating matrix, cosine similarity, and both recommenders as TODOs. It also decoded the ISO-8859-1 `u.item` catalog as ordinary UTF-8 text, started the genre flags one field too early (including `unknown`), and skipped only a rated movie ID—not an identical title stored under another ID.

## What changed in `fixed/`

- Implemented the user/movie rating matrix and User-Based and Item-Based recommendations.
- Decoded `u.item` with `TextDecoder('iso-8859-1')` and corrected the genre flag offset.
- Applied co-rated-only cosine with overlap weight `min(common ratings / 5, 1)`.
- Required at least three selected neighbors for a User-Based candidate and at least three distinct co-raters for an Item-Based candidate.
- Excluded titles already rated under another ID and removed duplicate titles from each Top-5.

The Item-Based support check counts each candidate rater once when that person also rated at least one movie in the active user’s history.

## Run the app

Serve the static files over HTTP so the browser can fetch the local data files:

```sh
cd week3/fixed
python3 -m http.server 8000
```

Open <http://localhost:8000>.

## Run checks and rebuild reports

From the `week3/` directory, run:

```sh
node eval/build_submission_reports.js
```

The script checks parsing and duplicate-title behavior, compares the optimized calculations with the actual recommenders for users 1 and 196, verifies one cosine similarity and one weighted prediction by hand, and regenerates four English reports:

- `results/before_fixes.md` — baseline and original issues;
- `results/stage_comparison.md` — the effect of each CF safeguard, including duplicate-title recommendations before and after;
- `results/analytics.md` — complexity, missing values, sparsity, and genre-vs-CF Top-5;
- `results/checks.md` — parsing checks and manual calculations.

The script uses only Node.js built-in modules; no packages need to be installed.

An independent recount in plain Python (no shared code with the app) checks the main numbers:

```sh
python3 eval/recount_check.py > results/recount_check.txt
```
