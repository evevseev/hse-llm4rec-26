# Week 5 — Matrix Factorization

This directory contains the MovieLens 100k matrix-factorization assignment, a working copy of the starter page, evaluation scripts, and saved reports. The original starter and the working page are kept in separate directories.

## Repository layout

- `original/` — unmodified course starter files and MovieLens data.
- `fixed/` — browser-ready working copy: the six matrix-factorization functions, reproducible training, minimum-item-support filtering, correct MovieLens title decoding, matrix-density display, and selected-checkpoint test RMSE display.
- `eval/` — Node.js runners and diagnostics. `package.json` and `package-lock.json` pin TensorFlow.js dependencies. The `node_modules/` directory is ignored by Git.
- `results/` — Markdown, JSON, and CSV outputs from the experiments. Reports state their seed, candidate pool, and evaluation split where relevant.

## Running the browser page

Serve `fixed/` over HTTP; `fetch()` will not load the data files reliably from `file://` URLs:

```bash
cd week5/fixed
python3 -m http.server 8000
```

Open <http://localhost:8000/>. The page prefers WebGL and falls back to the browser CPU backend. After **Train**, it displays the selected validation epoch, model test RMSE, and the training-mean test baseline. Browser execution and visual layout have not been checked in this environment; see [What remains unverified](#what-remains-unverified).

## Running tests and evaluations

Install the Node.js evaluation dependencies and run the built-in tests:

```bash
cd week5/eval
npm install
npm test
```

`npm test` runs the page's 11 self-checks and a same-seed repeatability check. The expected self-check result is **11 passed, 0 failed, 0 pending**.

Useful evaluation commands:

| Command | Purpose | Main output |
|---|---|---|
| `npm run run` | Run the base single-seed train/evaluate pipeline | `results/metrics.json`, `results/report.md` |
| `npm run support` | Train seeds `101`, `202`, and `303`; choose item-support threshold `N` on validation, then evaluate the selected threshold on test | `results/support-filter-report.md`, `results/support-filter.json`, `results/support-filter-validation-users.csv` |
| `npm run verify-ui` | Reproduce the browser-facing checks on MovieLens using seed `1` | `results/browser-issues-after.md`, `results/browser-issues-after.json` |
| `npm run audit-recall` | Compare `gather` and one-hot/`matMul` gradients on CPU; audit Recall candidate pools on a seed-1 model | `results/recall-semantics.md`, `results/recall-semantics.json` |
| `npm run discovery` | Compare seed-1 Top-10 lists for users `1` and `2` with their history | `results/discovery-seed1.md`, `results/discovery-seed1.json` |
| `npm run discovery-all` | Measure genre discovery, popularity, and list overlap for all users; does not use test ratings | `results/discovery-all-seed1.md`, `results/discovery-all-seed1.json` |

Every JavaScript file in `eval/` starts with `// Generated with an AI assistant`. The `node_modules/` ignore rule is in both `week5/.gitignore` and `eval/.gitignore`.

## Dataset and implementation

MovieLens contains **943 users**, **1,682 movies**, and **100,000 ratings**. The chronological split contains **79,619 train**, **9,596 validation**, and **10,785 test** ratings. The matrix has **100,000 / 1,586,126 = 6.3047%** observed user–movie cells, using only real user and movie IDs (`943 × 1,682`); the allocated array also includes zero-index padding.

The browser uses **16 factors**, default training parameters of **20 epochs**, learning rate **0.01**, regularization **0.05**, and batch size **64**. Its recommendation threshold is **N=20** train ratings per movie. The function-level default remains `N=1` for the existing self-check fixtures.

### Validation-selected item-support threshold

The support experiment averages Recall@10 over seeds `101`, `202`, and `303`. It uses a fixed validation target set: relevant validation ratings are those rated at least `4` whose movie occurs in train; a target hidden by the support threshold counts as a miss rather than disappearing from the denominator.

| Minimum train ratings `N` | Validation macro Recall@10 (mean ± sample SD) | Validation micro Recall@10 (mean) | Mean hits | Relevant targets filtered by `N` |
|---:|---:|---:|---:|---:|
| 1 | 0.013303 ± 0.001817 | 0.014521 | 67.0 | 0 |
| 5 | 0.017989 ± 0.002576 | 0.020445 | 94.3 | 66 |
| 10 | 0.022734 ± 0.002251 | 0.026152 | 120.7 | 168 |
| 20 | 0.029552 ± 0.001567 | 0.033232 | 153.3 | 392 |

Validation selected **N=20**. Its post-selection test Recall@10 averaged **0.024477 ± 0.001671** across the three seeds, with a mean of **152 hits among 5,142 train-known relevant test targets**. There were **13 unseen relevant movie IDs**, **294 distinct relevant IDs below N=20**, and **82 users without a relevant train-known test target**. The test split had been inspected in earlier diagnostics, so this is not a historically untouched holdout.

### Candidate-pool and `unseenIds` audit

On one deterministic seed-1 model (selected epoch **3**, validation RMSE **1.007781**), ranking the full **1,682-movie** catalog gave **0.014292 macro / 0.015325 micro Recall@10** over **5,155** relevant test ratings and **862** users. Ranking only the **1,611** movies present in train gave **0.014312 macro / 0.015364 micro** over **5,142** train-known targets and **861** users. On that shared target set, the full-catalog and train-only rankings both had **79 hits** and macro Recall@10 **0.014312**.

There are **100,000 unique user–movie pairs** in the ratings data: no test pair repeats a rating by the same user in train. In the implementation, `unseenIds` means distinct relevant test movie IDs absent from the **global train movie pool**; it does not mean an item previously rated by that same user. The 13 unseen IDs account for 13 relevant test rows in this dataset. The same-user overlap case described ambiguously in the assignment text does not occur here.

### Gradient implementation check

The CPU check selected rows `[2, 0, 2]` and compared the same MSE loss and gradients through `tf.gather` and one-hot selection followed by `matMul`. Both losses were **1.140966654**; maximum absolute gradient difference was **0** for both user and item factors. Executable `tf.gather` calls remain in `predictRating` and the TensorFlow path of `computeRMSEFor`; `trainMF` uses one-hot selection plus `matMul`.

## Browser issues found and fixes

- **The page had not applied N=20.** The recommendation button called `recommendTopK(user, 10)`, falling back to `N=1`. On the real split, *Bitter Moon* had **6** train ratings and *Aparajito* had **5**. The browser now passes `N=20` to Top-10 and Recall; the post-fix seed-1 check confirms every returned item meets the threshold.
- **Movie titles contained replacement characters.** `u.item` stores `é` as the single byte `e9`, while `Response.text()` decoded it as UTF-8. `fixed/data.js` now decodes the movie file as Windows-1252; `Misérables, Les (1995)` is restored correctly.
- **The matrix summary omitted occupancy.** It now reports **100,000 / 1,586,126 (6.30%)**.
- **The selected model's test RMSE was not displayed.** After selecting the validation checkpoint, the page now displays model test RMSE alongside the training-mean baseline. In the deterministic seed-1 WASM check, epoch **3** had validation RMSE **1.007781**, model test RMSE **1.061236**, and baseline test RMSE **1.228900**.

## Discovery and personalization

For the seed-1, `N=20` lists, a genre-discovery slot is one whose movie has at least one genre absent from the user's train+validation history. Across **943 users** and **9,430 recommendation slots**, **883 slots (9.36%)** introduced a genre absent from that user's history; **440 users** received at least one such item. The operational “obvious choice” definition is an item with only familiar genres that also falls in the train popularity top decile: **2,011 / 9,430 slots (21.33%)** met it.

The lists are not identical across users: **623** distinct movies appeared among recommendations, from **809** eligible movies (**77.01% coverage**); mean pairwise Top-10 Jaccard was **0.0312**, with **0.558 shared titles out of 10** on average. Mean popularity self-information was **10.223 bits per recommendation**. These genre labels and popularity values are proxies for taste expansion, not evidence that a user has never seen or heard of a movie.

## What remains unverified

- No browser was available here. The HTTP page still needs a manual visual check, including WebGL/CPU backend behavior, title rendering, the N=20 hint, matrix fill, and the post-training RMSE line.
- Browser metrics may differ slightly from Node/WASM because the browser may select WebGL or another backend.
- Movie-rating history and genre labels cannot establish actual awareness or viewing; “new genre” is an offline proxy.
- The existing test split was read in earlier analysis. Future tuning should select settings on validation and reserve a new chronological holdout for a fully untouched final evaluation.
