# Week 6 — Graph-Based Recommendations with Personalized PageRank

This submission implements a user–movie bipartite graph, global PageRank, Personalized PageRank (PPR), Top-10 retrieval evaluation, and a comparison with the supplied matrix-factorization (MF) model.

## Repository layout

- `original/` — untouched starter application, MovieLens 100K files, and original assignment instructions. Do not edit this directory.
- `fixed/` — completed browser application. It contains the seven assignment implementations, the MF regularization correction, Windows-1252 movie-title decoding, and a TensorFlow.js PPR worker used by browser evaluation.
- `eval/` — Node harnesses and independent diagnostic scripts. JavaScript files start with `Generated with an AI assistant`. `eval/node_modules/` is ignored by Git.
- `results/` — canonical assignment CSV outputs plus verification, run summaries, user examples, diagnostics, and clearly labelled before/after or counterfactual evidence.

Movie titles retain their source spelling and language. Comments and documentation authored for this submission are in English.

## Run instructions

### Browser application

From this directory, serve the project over HTTP; `fetch` and the PPR worker require an HTTP origin:

```sh
python3 -m http.server 8000
```

Open <http://localhost:8000/fixed/index.html>. Press **Build graph**, then **Evaluate Recall@10 — all four methods**. Evaluation selects alpha on validation before starting test comparison. Progress is reported while PPR runs in reusable TensorFlow.js workers. If workers cannot start, the application falls back to a responsive main-thread calculation.

### Node evaluation

Dependencies and exact versions are recorded in `eval/package.json` and `eval/package-lock.json`:

- `@tensorflow/tfjs` 4.22.0
- `@tensorflow/tfjs-backend-wasm` 4.22.0
- `@tensorflow/tfjs-node` 4.22.0

The measured Node run used Node.js 26.12.0 and npm 11.20.0. `eval/package-lock.json` records the exact resolved dependency tree.

Install and run from `week6/`:

```sh
npm install --prefix eval
HW6_WORKERS=8 node eval/run.js
```

The run executes the browser application's built-in self-checks, performs the validation alpha sweep, compares all four methods on test, trains MF, and regenerates `results/verification.json`, `results/results.csv`, `results/recommendations.csv`, and the supporting JSON outputs. PPR evaluation uses eight independent Node processes with TensorFlow.js WASM; MF uses the native TensorFlow.js Node backend.

Useful focused checks:

```sh
node eval/run.js --responsive-check
node eval/run.js --worker-smoke
node eval/run.js --profile
node eval/manual_ppr_user1.js
node eval/strict-index-test.js
node eval/two_user_demo.js
node eval/browser-worker-smoke.js
```

`browser-worker-smoke.js` runs the browser worker source through a Node VM shim; it does **not** replace a live browser check. The single-thread profile is a timing estimate from a 16-user sample, not a full single-thread experiment.

## Implementation and fixes

- The graph includes train-observed user and movie IDs, with binary undirected edges for ratings `>= 4.0`. Unobserved ratings are not treated as dislikes. Dangling probability is redistributed through the restart vector.
- PPR's public seed argument is a graph node index. The application adapter now maps a raw user ID to that index before calling PPR.
- MovieLens `u.item` includes a Windows-1252 byte for `é`; the loader decodes that file as Windows-1252 instead of UTF-8 replacement characters.
- The original MF loss regularized every parameter in the full factor tables on every mini-batch. The corrected loss regularizes the gathered batch embeddings and scales by batch size, preventing factor collapse.
- Evaluation previously used the slider alpha before doing the validation sweep, repeated PPR to calculate list popularity, and ran synchronously on the UI thread. The app now selects/caches validation alpha first, computes list popularity during the Recall pass, yields progress, caches graph tensors, and distributes user PPR walks to TensorFlow.js workers.
- Browser and Node MF scores are not bitwise reproducible across backends. The browser selects WebGL when available (CPU fallback); the Node evaluation uses the native `tensorflow` backend. Report each metric with its backend, checkpoint, and validation RMSE. Do not label the Node MF value as a browser result.

## Final Node-run data and results

The run loaded 100,000 ratings and 1,682 movie records. The per-user chronological split is 79,619 train / 9,596 validation / 10,785 test ratings. The train graph has 943 user nodes, 1,611 movie nodes, 2,554 total nodes, 45,602 positive edges, one zero-degree user, and 253 zero-degree movies. The split is chronological within each user, not globally time-consistent; MovieLens records ratings, not viewing sessions.

Validation Recall@10 selected **alpha = 0.50** (ties go to the smaller alpha):

| Alpha | Validation Recall@10 |
|---:|---:|
| 0.50 | 0.114483 |
| 0.70 | 0.104797 |
| 0.85 | 0.090021 |
| 0.95 | 0.073750 |

The test evaluation starts with 943 training users; one has no positive training edge. The common warm-user cohort contains 861 users. Reported exclusions are one user without a positive train edge, 13 relevant movie/user pairs outside the train candidate pool, and 82 users without an eligible relevant movie:

| Method | Test Recall@10 |
|---|---:|
| Popularity | 0.076023 |
| Global PageRank | 0.079693 |
| PPR (alpha 0.50) | 0.112189 |
| MF (Node backend `tensorflow`, checkpoint 3) | 0.020627 |

The selected MF checkpoint has validation RMSE 0.982288. Its result belongs to the native Node backend; the browser's MF result and best epoch can differ because the browser uses a different TensorFlow.js backend.

PPR convergence at alpha 0.50: global PageRank 19 iterations; PPR user 1 22 iterations; PPR user 2 21 iterations. All three met the `1e-6` tolerance.

## One-factor-at-a-time examples and decision

The §6.2 settings keep one factor fixed per comparison:

- A: user 1, alpha 0.85 (baseline), mean Top-10 train popularity 245.5.
- B: user 2, alpha 0.85 (seed changes only), mean popularity 254.9.
- C: user 1, alpha 0.50 (alpha changes only), mean popularity 228.4.

Common Top-10 movies: A/B **0**, A/C **7**, B/C **0**. The PPR-vs-Popularity Top-10 overlap is 6/10 for user 1 and 4/10 for user 2. Between-user overlap within a method is: Popularity 1, PageRank 1, PPR 1, MF 3. These are descriptive counts, not proof of improved personalization or discovery.

The recorded offline evidence supports **replacing MF with PPR in the current Top-10 surface**: PPR has the highest measured test Recall@10. The complete recommendation lists, train histories, overlap calculations, and rationale are in `results/two-user-demo.json`, `results/users-1-2-train-positive.csv`, `results/top10-overlap.json`, and `results/business-analysis.md`.

Offline Recall cannot establish current-session intent, playback starts/completion, satisfaction, retention, or revenue. Before rollout, run a sticky user/account-level A/B test: MF Top-10 control versus PPR alpha 0.50 treatment, same placement and candidate rules; use recommended-film playback starts within 24 hours as the primary outcome and total watch minutes per assigned user as a guardrail. Stable account-level assignment prevents users from crossing between methods across sessions/devices.

## Results inventory and status

Canonical deliverables:

- `results/verification.json` — 12 pass, 0 fail, 0 pending.
- `results/results.csv` — per-method test Recall@10, shared cohort, exclusions, selected alpha, and MF checkpoint/backend.
- `results/recommendations.csv` — user, method, alpha, rank, movie ID, title, genres, score, and training popularity for users 1 and 2.

Supporting diagnostics include `alpha-sweep.json`, `test-recall.json`, `run-summary.json`, `convergence.json`, `performance.json`, `mf-before.json`, `mf-after.json`, `mf-before-after.json`, `manual-ppr-user1.json`, and `strict-node-index-test.json`. The latter is a counterfactual: treating raw user IDs as node indices lowers test PPR Recall@10 to 0.052448; it is not the corrected result.

Not completed or not verified here: a live browser run of the latest Worker/CDN/WebAssembly path, a course-format report PDF, the course-required AI-session export, and the current grading guide/submission deadline. Confirm the course-specific requirements with the instructor. A real browser MF metric should be taken from that browser run and reported with its backend/checkpoint rather than substituted with the Node metric above.
