# HW4 — Association-Rule Analysis

## Method

All counts are basket counts over `N = 17,080` invoices. For each rule, count baskets containing A, B, and both, then compute:

- `support = count(A∪B) / N`;
- `confidence(A→B) = count(A∪B) / count(A)`;
- `lift(A→B) = confidence(A→B) / (count(B) / N)`.

The example counts below were independently recounted from the decoded baskets. Reproduce them with `node eval/verify.js`.

## The highest-lift rule is not automatically the most useful

The top rule in the 1% support / 30% confidence table is:

**HERB MARKER THYME (`22916`) → HERB MARKER ROSEMARY (`22917`)**

- `count(A∪B) = 176`, `count(A) = 186`, `count(B) = 190`;
- support: `176 / 17,080 = 1.0304%`;
- confidence: `176 / 186 = 94.62%`;
- baseline frequency of B: `190 / 17,080 = 1.1124%`;
- lift: `94.62% / 1.1124% = 85.06`.

This is a very strong relative association, but it reaches a narrow group: A occurs in only 186 baskets. Lift ranks association strength relative to the baseline; it does not account for reach, margin, inventory, or whether the recommendation would cause an extra purchase. This rule also falls below the selected 2% support threshold.

## Rule to test: complete a product collection

From the 2% support / 60% confidence table:

**GREEN REGENCY TEACUP AND SAUCER (`22697`) + ROSES REGENCY TEACUP AND SAUCER (`22699`) → PINK REGENCY TEACUP AND SAUCER (`22698`)**

- `count(A∪B) = 390`, `count(A) = 541`, `count(B) = 551`;
- support: `390 / 17,080 = 2.2834%`;
- confidence: `390 / 541 = 72.09%`;
- baseline frequency of B: `551 / 17,080 = 3.2260%`;
- lift: `72.09% / 3.2260% = 22.35`.

This has more joint baskets than the herb-marker example (390 versus 176) and passes the stricter support threshold. It is a candidate for a **“complete the collection” experiment**, not proof that a promotion will increase sales.

## A strong-looking rule to reject as a generic cross-sell

This rule is in the final table:

**ALARM CLOCK BAKELIKE RED (`22727`) → ALARM CLOCK BAKELIKE GREEN (`22726`)**

- `count(A∪B) = 530`, `count(A) = 877`, `count(B) = 784`;
- support: `530 / 17,080 = 3.1030%`;
- confidence: `530 / 877 = 60.43%`;
- baseline frequency of B: `784 / 17,080 = 4.5902%`;
- lift: `60.43% / 4.5902% = 13.17`.

The metrics establish strong co-occurrence, but they do not show that showing a green clock after a red one would cause an additional sale. These are two colors of the same product line; the invoices may reflect collectors, assortment orders, or wholesale purchases. I would reject an immediate, generic cross-sell launch based on this rule alone. It could still be tested as a second-color recommendation, measuring incremental units and margin as well as cannibalization.

For comparison, under the softer 0.5% / 10% settings, `ALARM CLOCK BAKELIKE GREEN → WHITE HANGING HEART T-LIGHT HOLDER` has 89 joint baskets, 0.5211% support, 11.35% confidence, and lift 0.9898. The consequent occurs in 11.47% of baskets overall, so the rule is slightly below baseline. This is a genuinely weak rule correctly excluded by `lift > 1`, but it is not one of the final-table rules and does not meet its confidence or support thresholds.

## Rule direction

For the teacup rule, `A = GREEN REGENCY + ROSES REGENCY` and `B = PINK REGENCY`. The two confidences use different denominators:

- `A→B`: baskets with **GREEN and ROSES** also contain PINK in `390 / 541 = 72.09%` of cases;
- `B→A`: baskets with **PINK** also contain both GREEN and ROSES in `390 / 551 = 70.78%` of cases.

The reverse rule is therefore **PINK REGENCY → GREEN REGENCY + ROSES REGENCY**. Lift is the same in either direction:

- `A→B`: `(390 / 541) / (551 / 17,080) = 22.35`;
- `B→A`: `(390 / 551) / (541 / 17,080) = 22.35`.

## Thresholds and final setting

| Minimum support | Frequent itemsets by size | Total itemsets | Rules at 30% confidence | Rules at 60% confidence |
|---:|---|---:|---:|---:|
| 1% | 1-item: 691; 2-item: 413; 3-item: 109; 4-item: 6 | 1,219 | 950 | 238 |
| 2% | 1-item: 242; 2-item: 51; 3-item: 1 | 294 | 96 | 20 |
| 3% | 1-item: 109; 2-item: 6 | 115 | 12 | 5 |

Increasing support removes less common itemsets: at 30% confidence, rules fall from 950 at 1% support to 12 at 3%. Increasing confidence also reduces the rule count, but does not change the frequent-itemset count.

The final setting is **2% support / 60% confidence**, yielding 20 rules. At 2% support, `ceil(0.02 × 17,080) = 342` is the minimum count threshold; it is not the observed minimum in the output. The smallest joint count among the 20 rules is **390**. This setting gives a compact table with stronger minimum co-occurrence counts than 1% / 30%, while the lower setting remains useful for exploration. The `lift > 1` filter removes none of the rules in the six 1–3% / 30–60% combinations. That is expected: the most frequent item occurs in 1,959 of 17,080 baskets (11.4696%), so any rule with confidence at least 30% has lift at least 2.6156.

## What the final 20 rules represent

All 20 directional rules group into same-product or same-collection variants:

| Product family | Directional rules |
|---|---:|
| Regency teacups | 9 |
| Lunch boxes | 2 |
| Garden kneeling pads | 2 |
| Bakelike alarm clocks | 3 |
| Paper chain kits | 1 |
| Jumbo bags | 2 |
| Hanging Heart T-light holders | 1 |
| **Total** | **20** |

These are not 20 independent discoveries: some are reverse directions or different splits of the same frequent itemset. The final table contains no cross-category rules. It suggests variant/collection affinity and catalogue structure. A “complete the collection” feature may fit; an ordinary complementary-product cross-sell is not supported by this table. Another color may be a substitute rather than an incremental item, so measure added units and margin and guard against cannibalization.

## Large-basket sensitivity and possible wholesale influence

There are 215 baskets (1.2588%) with at least 100 distinct items. The median basket has 16 items and the largest has 540. Basket size is only a proxy for wholesale: the export has no wholesale-customer label.

There are 3,309 distinct invoices containing at least one final-rule itemset; 154 of them (4.6540%) have at least 100 items. Large invoices are overrepresented among matching baskets compared with their 1.2588% share of all baskets, but remain a minority. No individual rule gets more than 10.94% of its joint count from large baskets.

As a sensitivity check, remove all 215 large baskets and recompute metrics using the remaining 16,865 as N. **18 of 20 rules** still pass 2% support, 60% confidence, and lift > 1. The two exceptions fail only the confidence threshold: `SPACEBOY LUNCH BOX → DOLLY GIRL LUNCH BOX` falls to 59.70%, and `GARDENERS KNEELING PAD KEEP CALM → GARDENERS KNEELING PAD CUP OF TEA` falls to 59.77%; their support and lift remain above threshold. Thus the table is not wholly driven by invoices with hundreds of items, although large invoices influence some counts. Without a customer-type field, the analysis cannot identify which are wholesale orders.

## Feature, limitation, and validation plan

A concrete experiment is a “complete the collection” cart slot: when the basket contains **GREEN and ROSES**, show **PINK REGENCY**. The main limitation is that the export contains invoice baskets without usable per-basket timestamps or purchase sequence. Co-occurrence does not tell which product came first and may reflect collection intent, merchandising, seasonality, discounts, or bulk orders. It does not establish incremental sales.

The current data cannot support a temporal holdout. Do not invent dates. Obtain later invoices with timestamps, freeze the rule and thresholds, then measure its support, confidence, lift, and joint count in the later period, including month and customer-type stability if available.

Then randomize eligible baskets containing GREEN and ROSES: treatment sees the PINK recommendation; control does not. Measure incremental PINK attach rate and margin, while monitoring total conversion and cannibalization. Set the minimum practical effect and sample size before the test; ship only if the treatment improvement is statistically convincing and guardrail metrics do not worsen. The dates, exposure logs, and experiment outcomes required for this plan are absent from the starter dataset.
