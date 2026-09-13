"""Canonical event schema — dataset-agnostic contract for the whole pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class EventContext:
    city: Optional[str] = None
    device: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


@dataclass
class CanonicalEvent:
    event_id: str
    session_id: str  # namespaced: "<track>:<raw_id>"
    timestamp: int  # UTC epoch seconds
    item_id: str
    event_type: str
    track: str = "trivago"
    context: EventContext = field(default_factory=EventContext)


def namespaced_key(track: str, raw_session_id: str) -> str:
    return f"{track}:{raw_session_id}"
