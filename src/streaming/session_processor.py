"""Session processor: timestamp-authority, atomic per-session Redis writes, 30-min sliding TTL."""
from __future__ import annotations

import json
import threading
from typing import Any, Dict

DEFAULT_TTL_SECONDS = 1800


class SessionProcessor:
    def __init__(self, redis_client: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.redis = redis_client
        self.ttl = ttl_seconds
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock_for(self, key: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())

    def _read(self, key: str) -> Dict[str, Any]:
        raw = self.redis.hgetall(key) or {}
        recent = raw.get("recent_items", "[]")
        try:
            items = json.loads(recent) if isinstance(recent, str) else list(recent)
        except (ValueError, TypeError):
            items = []
        last_ts = raw.get("last_ts", 0)
        try:
            last_ts = int(last_ts)
        except (ValueError, TypeError):
            last_ts = 0
        return {"recent_items": items, "city": raw.get("city"),
                "filters": raw.get("filters"), "last_event": raw.get("last_event"),
                "last_ts": last_ts, "seen": set(json.loads(raw.get("seen", "[]")))}

    def apply_event(self, event: Any) -> bool:
        ev = event.__dict__ if hasattr(event, "__dict__") and not isinstance(event, dict) else event
        key = str(ev["session_id"])
        ts = int(ev["timestamp"])
        eid = str(ev["event_id"])
        with self._lock_for(key):
            st = self._read(key)
            if eid in st["seen"]:
                return False  # duplicate redelivery → idempotent
            if ts < st["last_ts"]:
                return False  # stale event ignored (timestamp authority)
            items = st["recent_items"] + [str(ev.get("item_id", ""))]
            seen = st["seen"] | {eid}
            payload = {
                "recent_items": json.dumps(items[-50:]),
                "last_event": str(ev.get("event_type", "")),
                "last_ts": str(ts),
                "seen": json.dumps(sorted(seen)[-500:]),
            }
            if ev.get("city") is not None:
                payload["city"] = str(ev["city"])
            # Atomic single-pipeline write: recent_items + city + last_event + last_ts.
            pipe = self.redis.pipeline()
            pipe.hset(key, mapping=payload)
            pipe.expire(key, self.ttl)  # sliding TTL refresh
            if hasattr(pipe, "execute"):
                pipe.execute()
            self.redis.expire(key, self.ttl)
            return True

    def get_state(self, key: str) -> Dict[str, Any]:
        st = self._read(key)
        st.pop("seen", None)
        return st
