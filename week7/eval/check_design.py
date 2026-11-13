# Generated with an AI assistant. Design arithmetic only; no recommender is run.
import json
import math
from pathlib import Path

idcg = 1 + 1 / math.log2(3)
calls = {"development": 100, "main_a": 100, "main_b": 100}
total_calls = sum(calls.values())
result = {
    "status": "analytical design checks, not observed ranking performance",
    "pool_ceiling_example": {
        "eligible_relevant_items": 2,
        "relevant_items_in_pool": 1,
        "best_possible_hit_positions": [1],
        "maximum_dcg": 1,
        "idcg": idcg,
        "maximum_ndcg": 1 / idcg,
        "reason": "A reranker cannot output the second relevant item because it is absent from the pool.",
    },
    "call_budget": {
        **calls,
        "total": total_calls,
        "hour_seconds": 3600,
        "maximum_mean_seconds_per_call_ignoring_setup": 3600 / total_calls,
        "note": "Model loading and preprocessing reduce the available per-call allowance.",
    },
}
output = Path(__file__).resolve().parents[1] / "results" / "design_checks.json"
output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
