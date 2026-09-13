"""V1 baselines: popularity + item-to-item similarity (deterministic)."""
from __future__ import annotations

from typing import Any, Dict, List


def popularity_rank(inventory: List[Dict[str, Any]], k: int = 500) -> List[str]:
    ranked = sorted(inventory,
                    key=lambda it: (-it.get("pop", 0), str(it.get("item_id", ""))))
    return [str(it["item_id"]) for it in ranked[:k]]


def item_similarity_rank(session: Dict[str, Any],
                         inventory: List[Dict[str, Any]], k: int = 500) -> List[str]:
    recent = session.get("recent_items") or []
    city = session.get("city")
    scored = []
    for it in inventory:
        score = 0
        if city is not None and it.get("city") == city:
            score += 2
        if it.get("item_id") in recent:
            score -= 100  # do not re-recommend already-seen items first
        scored.append((score, it.get("pop", 0), str(it.get("item_id", ""))))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [t[2] for t in scored[:k]]
