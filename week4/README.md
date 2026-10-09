# Week 4 — Association Rules

This folder contains the HW4 basket-analysis starter and its completed implementation.

## What is included

- `original/` — untouched starter files.
- `fixed/` — completed implementation. Open `fixed/index.html` in a modern browser to use the page.
- `eval/benchmark.js` — runs the requested support/confidence settings, benchmarks the softest slider setting, and regenerates the CSV tables and benchmark summaries.
- `eval/verify.js` — runs the built-in checks plus exhaustive fixture, UI-rendering, direct-count, item-family, and large-basket checks.
- `eval/recount_check.py` — independently recounts the dataset and reported rules using Python's standard library.
- `results/analysis.md` — English business analysis, selected thresholds, limitations, and validation plan.
- `results/rules-*.csv` — rules with `lift > 1`, retained for analysis at 1%/30% and 2%/60%.
- `results/benchmark-summary.csv` and `results/benchmark.txt` — threshold counts and timings.
- `results/verification.txt` — saved verification output.
- `results/recount_check.txt` — saved output from the independent Python recount.

The page keeps every rule meeting the support and confidence sliders, as required, and sorts by joint basket count followed by lift. The exported analysis CSVs contain only rules with `lift > 1`.

## Run

From this directory, using Node.js (no package installation required):

```sh
node eval/benchmark.js
node eval/verify.js
python3 eval/recount_check.py > results/recount_check.txt
```

The benchmark regenerates its tables and summaries in `results/`. The verification script expects the 2%/60% table from the benchmark run and saves its full output to `results/verification.txt`. The Python check independently recomputes the threshold and rule counts and saves its output with the command above.

## Final setting and findings

The recommended analysis table uses **2% minimum support** and **60% minimum confidence**. It contains 20 directional rules, all with lift greater than 1. The support cutoff corresponds to at least 342 joint baskets; the smallest observed joint count in the table is 390.

All 20 rules describe variants within seven product families, so the strongest use case is testing collection-completion recommendations rather than assuming general cross-category cross-sell. Excluding invoices with at least 100 distinct products leaves 18 of the 20 rules above all three thresholds. The dataset has no usable per-invoice dates or wholesale-customer label, so temporal stability and wholesale-specific behavior require new data.
