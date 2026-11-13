# Session 1: Frozen LLM Reranking Plan

## Research question

For the homework's deterministic sample of 100 warm users, does a zero-shot open-weight LLM improve nDCG@10 over RRF on the same fixed candidate pool, using the same past-only FAR-Trans data fields in a different representation?

This is a planned study. No improvement is assumed.

## One fixed model and one fixed prompt

- Model: `Qwen/Qwen2.5-1.5B-Instruct`, open-weight, Apache-2.0.
- Immutable Hugging Face revision: `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`.
- Model card: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct
- Snapshot: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/tree/989aa7980e4cf806f80c7fef2b1adb7bc71aa306
- No fine-tuning, no API, no demonstrations, and no second model.
- Proposed environment: Python 3.11, PyTorch 2.6.0, Transformers 4.51.3; one FP16 model in eval and inference mode.
- One prompt template is written and frozen before the development pass. No prompt variants or prompt revisions.
- Greedy decoding: `do_sample=False`, `num_beams=1`, `max_new_tokens=96`. Require JSON with ten unique candidate aliases. Invalid output falls back to that user's RRF Top-10, is counted, and is not retried.

## Same data, different representation

The classical source rankings and the LLM use the same past-only transactions and as-of asset fields. RRF combines complete source ranks. The LLM receives those ranks plus a compact representation of the same history and CBF fields:

| Prompt part | Fields |
|---|---|
| History | Up to 20 most recent distinct past-Buy aliases; `buy_count`; `days_since_last_buy`; the starter's `feature_tokens` |
| Candidate | Opaque alias; `rank_latest_buy`; `rank_cbf`; `rank_popularity`; the same `feature_tokens` |
| Feature tokens | `assetCategory`, `assetSubCategory`, `sector`, `industry`, `marketID`, using the starter's tokenization and missing-value rule |

No customer IDs or profiles, asset names, raw ISINs, prices, profitability, transaction amounts, units or channels, sell events, later metadata, or external text are sent to the model. The classical rankings still use their complete histories; the LLM history is capped at 20 for a small prompt. This is a representation change, not a new information source.

The possible advantage is user-specific combination of recency, repeated buys, and categorical matches. RRF applies one fixed formula to all users. The LLM may recognize patterns across the same history and features that the fixed fusion misses. It may also fail to improve: CBF already represents category overlap, Latest Buy represents recency, Popularity represents a global preference, and a small untuned LLM may mishandle structured inputs. No method can retrieve a relevant asset missing from the frozen pool.

## Candidate pool and RRF control

Use the exact source rankings and candidate quotas in `session1_candidate_protocol.md`: complete past-only Latest Buy, CBF, and Popularity rankings over the eligible universe; up to 20, 20, and 10 candidates from those sources, respectively; deduplicate and fill to 50 by RRF. The RRF score is the sum of `1 / (60 + source_rank)` over the three complete rankings, with 1-based ranks. Keep the four required full-universe baselines in the eventual report: Popularity, CBF, Latest Buy, and Latest Buy or Sell.

## Development decision and untouched main test

Use one fixed prompt and one dev pass. Do not search prompt variants.

1. **Development:** cutoff `2021-05-01`, labels `[2021-05-01, 2021-05-31)`, 100 deterministic warm development users selected without labels and disjoint from the main cohort. One model call per user in canonical alias order.
2. **Decision:** keep the LLM as the proposed method only if dev nDCG@10 over all dev users exceeds RRF at full precision, dev nDCG@10 for nonempty truth is not lower than RRF, there is at most one malformed output, and the run stays within the time/cost cap. If there are too few nonempty-truth users to make this comparison useful, record the dev result as inconclusive and keep RRF as the safe choice. This is the only keep/drop decision.
3. **Main test:** the homework's deterministic 100 warm users, cutoff `2021-06-01`, labels `[2021-06-01, 2021-07-01)`. Freeze users, pools, prompt, checkpoint, and decoding before reading June labels. Make two passes: Run A in canonical alias order; Run B with candidate rows permuted per user using seed `2026`.

Publish both main-test outcomes, their difference, and per-user Top-10 overlap. Do not choose the better order, revise the method, or change the dev decision based on the main test. Run A is the predeclared canonical output; Run B is the order-sensitivity check. Main-test results remain reportable even when negative.

## Metrics and failure handling

- Primary: mean nDCG@10 over all 100 main-test users; empty truth is zero.
- Also report the nonempty-truth mean and count, candidate recall, failed/fallback outputs, and end-to-end inference time.
- Keep full precision for comparisons. Never remove users or failed cases.
- A malformed model response uses the RRF Top-10 for that user and counts as a failure. Do not retry.

## Time and cost cap

- One local or rented NVIDIA T4-class 16-GB GPU; one FP16 model instance; no API billing.
- Exactly 300 calls for the complete plan: 100 dev + 100 main Run A + 100 main Run B.
- Hard cap: one billable GPU-hour and US$5 total GPU rental. Target inference time is at most 45 minutes. Cache the checkpoint; stop at the cap and report incomplete if exceeded.
- Record actual hardware, software versions, checkpoint SHA, elapsed time, and failures. These are planned caps, not measured costs or speeds.

## Related work: four opened papers

| Study | Method / evidence | Limitation and connection |
|---|---|---|
| Sanz-Cruzado, Droukas, and McCreadie, "FAR-Trans: An Investment Dataset for Financial Asset Recommendation," IJCAI-2024 Workshop. https://arxiv.org/abs/2407.08692 | Describes the financial transaction, asset, and price release and evaluates transaction-, price-, and hybrid-based recommenders. | Nearest data/domain work; its protocol differs from the course's repeat-purchase teaching split and it does not test an LLM. |
| Hou et al., "Large Language Models are Zero-Shot Rankers for Recommender Systems," ECIR 2024. https://arxiv.org/abs/2305.08845 | Prompted LLM reranking on MovieLens and Amazon Games; studies history and candidate-order prompting. | Nearest method work. The authors report position and popularity biases; the datasets and item text differ from FAR-Trans. |
| Cormack, Clarke, and Buettcher, "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods," SIGIR 2009. https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf | Introduces RRF, `sum 1 / (k + rank)`, with `k=60` fixed during a pilot and held constant in validation; evaluates TREC runs and LETOR 3. | Supports the non-LLM control, not a claim that RRF is optimal for financial recommendation. The author copy was opened and read. |
| Bao et al., "TALLRec: An Effective and Efficient Tuning Framework to Align Large Language Model with Recommendation," RecSys 2023. https://arxiv.org/abs/2305.00447 | Tunes LLaMA for movie and book recommendation. | Shows task-specific tuning in other domains; our planned model is frozen and the data are financial. |

Among these four opened works, LLMRank is the nearest method study. This reading does not identify the exact comparison of an LLM, RRF, and a fixed FAR-Trans candidate pool under the homework protocol. This is a bounded observation, not a claim that no other work exists.

## RRF citation

G. V. Cormack, C. L. A. Clarke, and S. Buettcher, "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods," *Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval*, pp. 758-759, 2009. https://doi.org/10.1145/1571941.1572114.
