# Public Session 1 Research Materials

## Research question

For the homework's deterministic sample of 100 warm users, does one frozen open-weight LLM improve nDCG@10 over RRF on the same fixed FAR-Trans candidate pool, using existing past-purchase history and CBF feature fields?

## What has been checked

- Read the Session 1 instructions, shared-project scope, starter documentation, and starter interfaces. The four required full-universe baselines are Popularity, CBF, Latest Buy, and Latest Buy or Sell.
- Read the local public FAR-Trans release row for `transactionID=7590224`, its linked asset metadata, and a pre-cutoff price row. The customer identifier is omitted from the saved example.
- Checked the release values against the FAR-Trans paper's processing description. The amount `11000.0` equals `5000.0 * 2.2`; the paper describes estimated amounts and adjusted quantities, so the arithmetic is not treated as proof of original row-level provenance.
- Opened FAR-Trans, LLMRank, TALLRec, and the authors' RRF PDF. The RRF paper defines `sum 1/(k + rank)` and states that `k=60` was fixed after pilot selection.
- Read `eval/verify_evidence.py`, provided by another chat assistant, and ran it unmodified on the local CSVs with a temporary output path. Its rerun JSON matches `results/independent_verification.json` byte for byte; the saved SHA-256 values also match the current local CSVs. The comparison is recorded in `results/reproducibility_check.json`.
- The verification covers one source record and illustrative arithmetic only. It does not run the recommender, an LLM, or a ranking experiment. The script is not authored by this agent.

## What is only planned

- One model: `Qwen/Qwen2.5-1.5B-Instruct`, revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`.
- One prompt, frozen before development; no prompt variants or retries.
- Candidate quotas: up to 20 Latest Buy, 20 CBF, and 10 Popularity candidates, with RRF fill to 50.
- One 100-user development pass decides whether to keep the LLM method. The June main test uses two candidate-row orders; both results are published without choosing the better one.
- Total plan: 300 calls (100 dev + 100 main Run A + 100 main Run B), capped at one GPU-hour and US$5 GPU rental. These are limits, not measured costs or speeds.
- The recommender, model call, and experiments have not been implemented or run.

## Public materials

- `session1_plan_and_literature.md` - fixed study plan and four-paper reading table.
- `session1_candidate_protocol.md` - source rankings, 20/20/10 quotas, shared fields, and RRF control.
- `session1_data_example.md` and `session1_data_example.csv` - released record, field provenance, and leakage notes.
- `eval/verify_evidence.py` - source-check script provided by another chat assistant.
- `results/independent_verification.json` - that script's original saved output.
- `results/reproducibility_check.json` - comparison of the rerun with the saved output and current CSV hashes.

## How to continue

1. Keep the model revision, prompt, source definitions, quotas, and tie rules frozen before the June labels are inspected.
2. Make the keep/drop decision from the single earlier development pass. Do not use either June candidate order to tune the method.
3. If implementing later, report all four starter baselines, RRF, both LLM order results, nonempty-truth count, candidate recall, failures, runtime, and cost. Do not claim improvement unless the completed evaluation supports it.

This README lists the public research materials and does not report a completed model or recommendation experiment.
