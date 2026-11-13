# Generated with an AI assistant. Independent checks; no recommendation model is run.
import argparse
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cutoff = "2021-06-01"
    transactions = read_rows(args.data_dir / "transactions.csv")
    matches = [r for r in transactions if r["transactionID"] == "7590224"]
    assert len(matches) == 1
    record = matches[0]
    assert (record["ISIN"], record["transactionType"], record["timestamp"]) == (
        "GRS434003000", "Buy", "2020-03-27"
    )
    assert record["timestamp"] < cutoff and int(record["transactionID"]) >= 0
    asset_rows = [r for r in read_rows(args.data_dir / "asset_information.csv")
                  if r["ISIN"] == record["ISIN"] and r["timestamp"][:10] < cutoff]
    asset = max(asset_rows, key=lambda r: r["timestamp"])
    prices = [r for r in read_rows(args.data_dir / "close_prices.csv")
              if r["ISIN"] == record["ISIN"] and r["timestamp"][:10] < cutoff
              and float(r["closePrice"]) > 0]
    price = max(prices, key=lambda r: r["timestamp"])
    buy_prices = [r for r in prices if r["timestamp"] == record["timestamp"]]
    assert len(buy_prices) == 1
    buy_price = float(buy_prices[0]["closePrice"])
    amount_from_price = float(record["units"]) * buy_price
    assert amount_from_price == float(record["totalValue"])
    assert asset["assetName"] == "PPC SA"
    assert price["timestamp"] == "2021-05-31" and price["closePrice"] == "9.06"
    public_fields = ("ISIN", "transactionID", "transactionType", "timestamp")
    result = {
        "status": "verification only; no model inference or ranking experiment",
        "source": "https://researchdata.gla.ac.uk/1658/1/FAR-Trans.zip",
        "cutoff": cutoff,
        "matching_transaction_records": len(matches),
        "raw_transaction_fields": {k: record[k] for k in public_fields},
        "asset_metadata": {k: asset[k] for k in (
            "ISIN", "assetName", "assetCategory", "assetSubCategory", "marketID",
            "sector", "industry", "timestamp")},
        "latest_positive_price_before_cutoff": price,
        "days_since_example_buy": (date.fromisoformat(cutoff) -
                                   date.fromisoformat(record["timestamp"])).days,
        "released_amount_check": {
            "units": record["units"], "same_day_close_price": buy_prices[0]["closePrice"],
            "released_total_value": record["totalValue"], "product": amount_from_price,
            "caveat": "Matches the paper's estimation rule; arithmetic alone does not establish row-level provenance."},
        "rrf_arithmetic_example": {
            "label": "illustrative source ranks, not measured user recommendations",
            "ranks": [1, 3, 5], "constant": 60,
            "score": sum(1 / (60 + rank) for rank in [1, 3, 5])},
        "ndcg_arithmetic_example": {
            "label": "illustrative binary labels, not an observed recommendation result",
            "relevant_total": 2, "hit_positions": [2],
            "dcg": 1 / math.log2(3), "idcg": 1 + 1 / math.log2(3),
            "ndcg": (1 / math.log2(3)) / (1 + 1 / math.log2(3))},
        "source_sha256": {name: hashlib.sha256((args.data_dir / name).read_bytes()).hexdigest()
                          for name in ["transactions.csv", "asset_information.csv", "close_prices.csv"]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
