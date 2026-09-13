"""Trivago Track A adapter → canonical event."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from src.data.schemas import CanonicalEvent, EventContext, namespaced_key


def normalize_trivago(raw: Dict[str, Any]) -> CanonicalEvent:
    session_id = namespaced_key("trivago", str(raw["session_id"]))
    filters = raw.get("filters") or raw.get("current_filters")
    context = EventContext(
        city=raw.get("city"),
        device=raw.get("device"),
        filters=dict(filters) if isinstance(filters, dict) else None,
    )
    return CanonicalEvent(
        event_id=str(raw.get("event_id") or uuid.uuid4().hex),
        session_id=session_id,
        timestamp=int(raw["timestamp"]),
        item_id=str(raw.get("item_id") or raw.get("hotel_id") or ""),
        event_type=str(raw.get("event_type") or raw.get("action_type") or "click"),
        track="trivago",
        context=context,
    )
