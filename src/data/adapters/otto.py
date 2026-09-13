"""OTTO Track B adapter → canonical event (null context is valid)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from src.data.schemas import CanonicalEvent, EventContext, namespaced_key


def normalize_otto(raw: Dict[str, Any]) -> CanonicalEvent:
    session_id = namespaced_key("otto", str(raw["session_id"]))
    # OTTO has no city/device/filters — nulls are valid, downstream is null-safe.
    context = EventContext(city=None, device=None, filters=None)
    return CanonicalEvent(
        event_id=str(raw.get("event_id") or uuid.uuid4().hex),
        session_id=session_id,
        timestamp=int(raw["timestamp"]),
        item_id=str(raw.get("item_id") or raw.get("article_id") or raw.get("order_id") or ""),
        event_type=str(raw.get("event_type") or "click"),
        track="otto",
        context=context,
    )
