"""Session feature builder — null-safe, consumes canonical state only."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_session_features(session: Dict[str, Any]) -> Dict[str, Any]:
    recent: List[str] = list(session.get("recent_items") or [])
    city: Optional[str] = session.get("city")
    filters = session.get("filters")
    return {
        "recent_items": recent,
        "city": city,
        "filters": dict(filters) if isinstance(filters, dict) else None,
        "n_recent": len(recent),
        "last_item": recent[-1] if recent else None,
    }
