"""Automated quality gate: strict ≥ on metrics, latency + error ceilings."""
from __future__ import annotations

from typing import Mapping

P95_MAX_MS = 100.0
ERR_MAX = 0.01


def evaluate_gate(challenger: Mapping[str, float], champion: Mapping[str, float],
                  p95_ms: float, err_rate: float) -> dict:
    legs = {
        "ndcg": float(challenger.get("ndcg@10", 0)) >= float(champion.get("ndcg@10", 0)),
        "recall": float(challenger.get("recall@20", 0)) >= float(champion.get("recall@20", 0)),
        "latency": float(p95_ms) <= P95_MAX_MS,
        "error": float(err_rate) <= ERR_MAX,
    }
    passed = all(legs.values())
    return {"status": "PASS" if passed else "FAIL",
            "legs": legs, "stage_change": bool(passed)}
