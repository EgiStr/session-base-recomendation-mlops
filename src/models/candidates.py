"""Candidate retrieval: narrow inventory to ≤500, never empty when possible."""
from __future__ import annotations

from typing import Any, Dict, List

from src.models.baseline import item_similarity_rank, popularity_rank

MAX_CANDIDATES = 500


def generate_candidates(session: Dict[str, Any],
                        inventory: List[Dict[str, Any]],
                        k: int = MAX_CANDIDATES) -> List[str]:
    if not inventory:
        return []
    city = session.get("city")
    if city is not None:
        segment = [it for it in inventory if it.get("city") == city]
    else:
        segment = list(inventory)
    if segment:
        cands = item_similarity_rank(session, segment, k=k)
    else:
        # Empty segment → global popularity fallback (never empty when inventory exists).
        cands = popularity_rank(inventory, k=k)
    return cands[:k]  # short lists pass through as-is, no padding
