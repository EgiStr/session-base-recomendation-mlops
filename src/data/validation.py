"""Batch validation → quarantine report (corrupt data never enters features)."""
from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List

from src.data.schemas import CanonicalEvent

LATE_ARRIVAL_MAX_AGE_S = 7 * 86400


def validate_batch(batch: Iterable[CanonicalEvent], now: int | None = None) -> Dict[str, Any]:
    now = now if now is not None else int(time.time())
    per_check: Dict[str, int] = {"schema": 0, "timestamp": 0, "duplicate": 0,
                                 "late_arrival": 0, "id": 0, "type": 0}
    clean: List[CanonicalEvent] = []
    seen: set[str] = set()
    quarantined = 0

    for ev in batch:
        bad: str | None = None
        if not isinstance(ev, CanonicalEvent):
            bad = "schema"
        elif not isinstance(ev.timestamp, int) or isinstance(ev.timestamp, bool):
            bad = "timestamp"
        elif not ev.event_id or not ev.session_id or not ev.item_id:
            bad = "id"
        elif not isinstance(ev.event_type, str) or not ev.event_type:
            bad = "type"
        elif ev.event_id in seen:
            bad = "duplicate"
        elif now - ev.timestamp > LATE_ARRIVAL_MAX_AGE_S:
            bad = "late_arrival"
        if bad:
            per_check[bad] += 1
            quarantined += 1
            continue
        seen.add(ev.event_id)
        clean.append(ev)

    return {"quarantined": quarantined, "per_check": per_check, "clean": clean}
