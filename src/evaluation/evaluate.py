"""Offline evaluation: Recall@K / NDCG@K / MRR@K, means over 3 fixed seeds."""
from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Sequence

SEEDS = [42, 7, 123]


def _dcg(hits: Sequence[int], k: int) -> float:
    return sum(h / math.log2(i + 2) for i, h in enumerate(hits[:k]) if h)


def recall_at_k(ranked: Sequence[str], relevant: set, k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def ndcg_at_k(ranked: Sequence[str], relevant: set, k: int) -> float:
    hits = [1 if it in relevant else 0 for it in ranked]
    ideal = sorted(hits, reverse=True)
    denom = _dcg(ideal, k)
    return _dcg(hits, k) / denom if denom else 0.0


def mrr_at_k(ranked: Sequence[str], relevant: set, k: int) -> float:
    for i, it in enumerate(ranked[:k]):
        if it in relevant:
            return 1.0 / (i + 1)
    return 0.0


def evaluate(ranked: Mapping[str, Sequence[str]],
             relevant: Mapping[str, set], k: int = 10) -> Dict[str, Any]:
    per_seed = []
    for _ in SEEDS:  # deterministic metrics; seeds recorded for comparability
        ndcg = sum(ndcg_at_k(ranked[q], set(relevant.get(q, set())), 10) for q in ranked)
        rec = sum(recall_at_k(ranked[q], set(relevant.get(q, set())), 20) for q in ranked)
        mrr = sum(mrr_at_k(ranked[q], set(relevant.get(q, set())), 10) for q in ranked)
        n = max(len(ranked), 1)
        per_seed.append({"ndcg@10": ndcg / n, "recall@20": rec / n, "mrr@10": mrr / n})
    return {
        "ndcg@10": sum(s["ndcg@10"] for s in per_seed) / len(per_seed),
        "recall@20": sum(s["recall@20"] for s in per_seed) / len(per_seed),
        "mrr@10": sum(s["mrr@10"] for s in per_seed) / len(per_seed),
        "seeds": list(SEEDS),
    }


def compare(challenger: Mapping[str, float] | None,
            baseline: Mapping[str, float] | None) -> Dict[str, Any]:
    if not baseline:
        return {"status": "BLOCKED",
                "reason": "no baseline metrics for track — establish V1 first"}
    return {"status": "READY",
            "delta_ndcg": float(challenger.get("ndcg@10", 0)) - float(baseline.get("ndcg@10", 0))}
