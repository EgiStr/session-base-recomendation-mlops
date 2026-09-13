"""Ingestion entrypoint: raw rows → canonical → validated."""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

from src.data.schemas import CanonicalEvent
from src.data.validation import validate_batch


def ingest(raw_rows: Iterable[Dict[str, Any]],
           adapter: Callable[[Dict[str, Any]], CanonicalEvent]) -> Dict[str, Any]:
    events: List[CanonicalEvent] = [adapter(r) for r in raw_rows]
    return validate_batch(events)
