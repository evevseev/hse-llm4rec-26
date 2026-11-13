# FAR-Trans: actual record, field provenance, and leakage audit

**Source:** official FAR-Trans release, local `data/transactions.csv`, line 2. The associated asset row is in `data/asset_information.csv`, line 338. The local CSV is a processed public release, not the bank's raw log.

**Record ID:** `transactionID=7590224` (not a customer identifier).
**Anonymization:** the `customerID` value is omitted below. Other transaction-row values are transcribed verbatim from the released CSV.

## Released transaction row

Header: `customerID,ISIN,transactionID,transactionType,timestamp,totalValue,units,channel,marketID`

```text
[ANONYMIZED],GRS434003000,7590224,Buy,2020-03-27,11000.0,5000.0,Internet Banking,XATH
```

This is an actual released row. It is only an illustration and does not establish that its customer is among the homework's 100 evaluated users.

## Linked published asset metadata

The released `asset_information.csv` row for the same ISIN is:

```text
GRS434003000,PPC SA,Stock,Large Cap,XATH,Utilities,Utilities - Renewable,2018-01-02
```

These are selected columns, in their original order: `ISIN,assetName,assetCategory,assetSubCategory,marketID,sector,industry,timestamp`. The dataset README describes these as asset information and says the timestamp is the last update date. The paper says asset type, subtype, names, market, and available sector/industry information were obtained from public sources; they are not all original customer-transaction fields.

The released `close_prices.csv` has this row at line 279400:

```text
GRS434003000,2021-05-31,9.06
```

It is positive and dated strictly before the teaching cutoff `2021-06-01`, so it passes the starter's price-based eligibility check. The paper describes cleaning and adjustment of price data (including gap estimation and outlier/currency/split handling); the released row should therefore be described as a **published processed price**, not asserted to be an untouched raw exchange observation. It is used for eligibility only, not sent to the ranker.

## Field provenance and planned use

The distinction below is between the original kind of information, the value in the released CSV, and transformations documented by the authors. The release does not provide a per-cell provenance flag, so where a transformation could have affected this particular row, that uncertainty is stated rather than inferred away.

| Field/value | Provenance supported by the paper/release | Recommendation use |
|---|---|---|
| `customerID=[ANONYMIZED]` | Customer identifiers in FAR-Trans are anonymized. | Internal history grouping only; never send the identifier to the LLM. |
| `ISIN=GRS434003000` | Asset identifier in the published transaction and asset files; no row-level transformation is documented for this value. | Join transaction to asset and map the opaque candidate alias back to the allowed output ID locally; do not send the ISIN to the LLM. |
| `transactionID=7590224` | Positive ID in the released row. The starter excludes negative transaction IDs as reconstructed initial positions. The paper documents that some initial-position buys were reconstructed; the release does not otherwise expose row-level lineage. | Apply the starter's negative-ID exclusion; do not send the ID to the LLM. This row is retained under that rule, but its full source lineage is not independently recoverable from the paper. |
| `transactionType=Buy` | Transaction types are buy/sell events in the source data. The paper also describes added synthetic buys for some initial positions; this row's positive ID means it is not flagged as reconstructed by the starter rule. | Include in the past-Buy history. The prompt represents it through an opaque asset alias, count, recency, and existing feature tokens rather than a raw transaction row. |
| `timestamp=2020-03-27` | Date in the released row. The paper says dates outside available price coverage were moved to the closest date with a price. A same-day price row exists, but that fact alone does **not** establish whether this transaction date was moved or otherwise transformed; the release has no row-level provenance flag. | Use internally for source ranks and derive `days_since_last_buy` for the compact prompt history. |
| `units=5000.0` | Quantity in the released row. The paper says quantities were adjusted to account for stock splits and that synthetic transactions were added in some cases; no row-level flag identifies whether this quantity was adjusted. | Not needed by the proposed ranker; do not send it. |
| `totalValue=11000.0` | Do **not** label as independently observed. The paper says transaction values were estimated as quantity times closing price to address price inconsistencies. For this row, `5000.0 * 2.2 = 11000.0`; the released close price for this ISIN on `2020-03-27` is `2.2`. | Not used by the starter or the planned ranker; do not send it. |
| `channel=Internet Banking` | Channel is one of the transaction fields described in the paper's source log. No channel transformation is reported. | Not used by the starter or planned ranker; do not send it. |
| Transaction-row `marketID=XATH` | Present in the released CSV; the paper does not specify whether this transaction-level field was copied or derived. | Not used by the starter; do not send it. The asset metadata's `marketID` is a separate feature. |
| Asset metadata `assetName=PPC SA`, `assetCategory=Stock`, `assetSubCategory=Large Cap`, `marketID=XATH`, `sector=Utilities`, `industry=Utilities - Renewable` | Published asset descriptors, with row timestamp `2018-01-02`; the paper attributes asset information to public sources. | `assetCategory`, `assetSubCategory`, `marketID`, `sector`, and `industry` are the five existing CBF token fields. They can appear as `feature_tokens` for history and candidates. Do not send `assetName` or any new description. |
| `closePrice=9.06` on `2021-05-31` | Published processed price. Row-level raw-versus-imputed status is not supplied. | Eligibility check only; never a ranker feature. |

## Leakage and preprocessing check

- Teaching cutoff: `2021-06-01`. The transaction date `2020-03-27` is strictly before it.
- The selected asset metadata row is dated `2018-01-02`, before cutoff. The starter must still select the latest metadata row **strictly before** cutoff, rather than backfilling a later version.
- The price used for eligibility is dated `2021-05-31`, before cutoff. The paper describes price cleaning that can use later observations in some cleaning decisions; the released file has no row-level flag showing whether this particular price was changed. The starter uses it only in its frozen eligibility check, not as a recommendation score or LLM input.
- FAR-Trans is a processed release: the paper documents synthetic initial-position transactions, stock-split quantity adjustments, some date changes, estimated transaction values, and processed prices. For this selected row, the positive transaction ID passes the starter's explicit reconstruction filter. The same-day price does not prove that the date was never moved. The released total value matches the paper's quantity-times-price estimation rule; quantity-level and complete row-level lineage remain unknown.
- This is a source/protocol check, not a recommender run or result. The metric measures prediction of observed future purchases, not profit or investment suitability.

Under the proposed experiment, the LLM sees an opaque alias, the three candidate source ranks, the compact past-Buy history (`buy_count`, `days_since_last_buy`, and the existing CBF tokens), and the same CBF tokens for candidates. No profile, raw identifier, asset name, or external description is copied into its prompt.

## References

J. Sanz-Cruzado, N. Droukas, and R. McCreadie, "FAR-Trans: An Investment Dataset for Financial Asset Recommendation," IJCAI-2024 Workshop on Recommender Systems in Finance, 2024. [arXiv:2407.08692](https://arxiv.org/abs/2407.08692).

University of Glasgow, "FAR-Trans: An Investment Dataset for Financial Asset Recommendation," dataset record and README, [DOI: 10.5525/gla.researchdata.1658](https://doi.org/10.5525/gla.researchdata.1658).
