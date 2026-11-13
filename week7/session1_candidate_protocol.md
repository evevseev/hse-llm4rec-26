# Session 1 proposal: common candidate pool and history-aware LLM reranking

## Goal

Compare a zero-shot LLM's ordering with Reciprocal Rank Fusion (RRF) on exactly the same fixed candidate pool and the same underlying past-only fields, represented differently. RRF uses the three source rankings; the LLM also sees the transaction history and the categorical feature tokens used by CBF. This tests whether the LLM can combine those existing signals differently; it does **not** test new descriptions, profiles, or external knowledge.

## Source rankings over the complete eligible universe

Build all three rankings from information strictly before the cutoff, over the same eligible-asset universe. Assign 1-based ranks to every eligible asset; therefore each candidate has a rank in all three sources.

1. **Latest Buy:** assets with at least one past Buy are ordered by their latest Buy date, newest first, ties by ascending ISIN. Remaining eligible assets follow in Popularity order (Popularity ties by ISIN). Compute this complete ranking over all eligible assets for source ranks and RRF; take its first 20 for the candidate quota. The required reported `latest_buy` baseline remains the starter's Top-10 output.
2. **CBF:** use the starter's historical-Buy counts and as-of asset tokens (`assetCategory`, `assetSubCategory`, `sector`, `industry`, `marketID`); order by descending CBF score, ties by ascending ISIN. Preserve the starter's Popularity fallback if the CBF scores are all zero.
3. **Popularity:** use the starter's distinct historical buying-user count per asset; order by descending count, ties by ascending ISIN.

## Candidate pool: exact quotas

For each of the same 100 warm users and same cutoff:

1. Take **up to 20 from Latest Buy, up to 20 from CBF, and up to 10 from Popularity**, in that source-priority order.
2. Deduplicate as items are added. Thus the quotas total at most 50, not 20 from each of three sources.
3. If fewer than 50 unique items remain, fill to 50 using the highest-scoring remaining eligible assets under the RRF score below. If fewer than 50 eligible assets exist, use the entire eligible set.
4. Freeze the pool before evaluating labels. Candidate recall against future purchases is an evaluation diagnostic only; those labels never enter pool construction.

## RRF order

Following Cormack, Clarke, and Buettcher (2009), score each candidate with its ranks in the **three complete source rankings**:

```text
RRF(item) = 1/(60 + rank_latest_buy(item))
          + 1/(60 + rank_cbf(item))
          + 1/(60 + rank_popularity(item))
```

Sort by descending RRF score. Break score ties by ascending ISIN when constructing the pool; for the final within-pool order, use the same opaque candidate alias supplied to the LLM as the tie-break. The constant 60 is the conventional setting used in the original RRF work; it is fixed in advance and not tuned on evaluation labels.

## Shared source data and LLM representation

All fields come from the same past-only transaction and as-of asset data used by the classical methods. The LLM gets a different representation of these existing signals, not additional data:

- **History:** up to 20 distinct previously bought assets, ordered by latest past Buy; each row has an opaque `asset_alias`, historical `buy_count`, `days_since_last_buy`, and that asset's `feature_tokens`.
- **Each candidate:** opaque `candidate_alias`, the three 1-based ranks from the complete source rankings (`rank_latest_buy`, `rank_cbf`, `rank_popularity`), and the same `feature_tokens` used by CBF.
- **`feature_tokens`:** generated exactly from the starter's existing fields `assetCategory`, `assetSubCategory`, `sector`, `industry`, and `marketID`, including the starter's missing-value handling. No free-text description is added.

RRF uses the three ranks for each candidate; its source rankings were computed from the complete past history and the same CBF tokens over the full eligible universe. The LLM gets those same candidate ranks plus the last 20 past purchases and categorical tokens. It can therefore combine recency, repeat counts, and the existing CBF similarity signal in a different representation, but it gets no profile, field, or external source unavailable to the classical pipeline. The history is capped at 20 for prompt length; the classical rankings still use their complete histories.

Do **not** send customer IDs, customer profiles, `assetName`/`assetShortName`, raw ISINs, prices, profitability, transaction amounts/units/channels, sell events, later metadata, or external descriptions/news. The aliases map to ISINs only outside the model. The LLM returns a Top-10 permutation of candidate aliases, which is mapped back to ISINs locally. This is not a suitability or return-prediction task.

For each user, assign aliases by a deterministic pseudorandom mapping and keep that mapping fixed across runs. Run A serializes aliases in canonical order. Run B shuffles the rows with a fixed per-user seed; the rank tuples and candidate set do not change. This changes only prompt position and tests order sensitivity.

Use one English prompt, frozen before the development pass. There are no prompt variants or retries: one 100-user development pass and two 100-user main-test passes make 300 calls total. The development pass alone decides whether to keep the LLM method. Publish both main-test orders without selecting the better one.

## References

G. V. Cormack, C. L. A. Clarke, and S. Buettcher, "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods," *Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval*, pp. 758-759, 2009. [https://doi.org/10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114).

## Status

This is a proposed protocol, not an official course setting or measured result. The full Latest Buy ranking for pool creation and the frozen common-pool interface will require future starter changes; neither has been implemented here.
