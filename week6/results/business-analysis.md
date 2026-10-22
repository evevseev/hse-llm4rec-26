# Deployment recommendation

## Evidence used

- MovieLens 100K, per-user chronological 80/10/10 split.
- Shared warm-user test cohort: 861 users; same training-movie candidate pool and test exclusions for all methods.
- PPR alpha selected on validation: 0.50 (validation Recall@10 0.114483).
- Test macro Recall@10: popularity 0.076023, global PageRank 0.079693, PPR 0.112189, MF 0.020627.
- PPR and MF example lists for users 1 and 2, their positive train histories and training popularity are in `two-user-demo.json`, `top10-users-1-2.json`, and `users-1-2-train-positive.csv`.
- The Node MF run used the native TensorFlow backend; the browser selects WebGL when available (otherwise CPU). Use the metric, validation checkpoint and backend from one consistent run in a final report; do not present the Node MF value as a browser measurement.

## Decision

Replace MF with PPR in the current Top-10 recommendation surface, using the validation-selected alpha 0.50. PPR has the strongest measured retrieval on the shared test cohort (0.112189 versus 0.020627 for the Node MF run). The user lists show PPR is not simply the popularity Top-10: it shares 6/10 films with popularity for user 1 and 4/10 for user 2. Across users, PPR Top-10 lists share one movie; MF lists share three. MF lists have lower mean training popularity (87.0 and 85.9 versus PPR's 228.4 and 226.7), but low popularity alone does not demonstrate discovery value. No genre-fit claim is made here; the train histories are supplied as context, not as a measured genre-match metric.

## Top-10 overlap and popularity

PPR/popularity common-film counts: user 1, 6/10 (`Fargo`, `Contact`, `English Patient`, `Schindler's List`, `One Flew Over the Cuckoo's Nest`, `Casablanca`); user 2, 4/10 (`Return of the Jedi`, `Twelve Monkeys`, `Silence of the Lambs`, `Raiders of the Lost Ark`).

Common movies between users 1 and 2 within each method: popularity 1 (`Schindler's List`); global PageRank 1 (`Star Trek: First Contact`); PPR 1 (`Trainspotting`); MF 3 (`Lawrence of Arabia`, `The Third Man`, `Casablanca`). Mean popularity for each user's Top-10 by method is in `top10-overlap.json`.

## What the offline test cannot show

The chronological rating split does not measure current-session intent, whether a recommendation is played or completed, satisfaction, retention, or revenue. It is a warm-user retrieval test, not evidence of causal product impact.

## Online experiment

Randomly assign eligible accounts once, at user/account level, to either the existing MF Top-10 or PPR Top-10 (alpha 0.50), keeping placement, candidate pool and presentation identical. Use recommended-film playback starts within 24 hours per exposed user as the primary outcome; use total watch minutes per assigned user as a guardrail. Keep assignment sticky across sessions and devices so one user does not see both algorithms during the experiment.
