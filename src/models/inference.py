"""Inference helpers: ranker-backed + popularity fallback (never raises to user)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

log = logging.getLogger("triprank.inference")


def score_candidates(session_id: str, candidates: List[str], ranker: Any,
                     k: int = 20) -> tuple[List[Dict[str, Any]], str]:
    """Returns (items, model_version). Falls back gracefully on any failure."""
    try:
        if ranker is None:
            raise RuntimeError("no ranker loaded")
        ordered = ranker.recommend(session_id, candidates, k=k)
        version = getattr(ranker, "version", "ranker-v1")
        items = [{"item_id": str(i), "score": round(1.0 - idx * 0.01, 4)}
                 for idx, i in enumerate(list(ordered)[:k])]
        return items, str(version)
    except Exception as exc:  # graceful degradation — never 5xx
        log.error("inference failed session=%s expected=%s err=%s",
                  session_id, getattr(ranker, "version", "?"), exc)
        fb = [{"item_id": str(i), "score": 0.5} for i in candidates[:k]]
        return fb, "fallback"
