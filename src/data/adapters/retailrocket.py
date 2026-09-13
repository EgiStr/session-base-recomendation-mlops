"""RetailRocket Track adapter → canonical event.

Maps: view → click (label 0), addtocart → cart (label 1),
transaction → order (label 2). Null city/device/filters valid (H1).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

from src.data.schemas import CanonicalEvent, EventContext, namespaced_key

EVENT_MAP = {"view": "click", "addtocart": "cart", "transaction": "order"}
LABEL_MAP = {"view": 0, "addtocart": 1, "transaction": 2}


def normalize_retailrocket(raw: Dict[str, Any]) -> CanonicalEvent:
    session_id = namespaced_key("retailrocket", str(raw["visitorid"]))
    ts_ms = int(raw["timestamp"])
    return CanonicalEvent(
        event_id=str(raw.get("event_id") or uuid.uuid4().hex),
        session_id=session_id,
        timestamp=ts_ms // 1000,  # ms → UTC epoch seconds
        item_id=str(raw["itemid"]),
        event_type=EVENT_MAP.get(str(raw.get("event", "view")), "click"),
        track="retailrocket",
        context=EventContext(city=None, device=None, filters=None),
    )


def label_for(event_type: str) -> int:
    inv = {"click": 0, "cart": 1, "order": 2}
    return inv.get(event_type, 0)
