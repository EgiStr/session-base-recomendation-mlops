# tests/streaming/test_session_processor.py
# Given Redis recent_items=[H10,H21] last_ts=T / When click H33 ts=T+1 / Then atomic state
from src.streaming.session_processor import SessionProcessor


class FakeRedis:
    def __init__(self): self.store, self.ttls = {}, {}
    def pipeline(self): return self
    def __enter__(self): return self
    def __exit__(self, *a): self._flush(); return False
    def _flush(self):
        for op in getattr(self, "_ops", []): op()
        self._ops = []
    def execute(self): self._flush()
    def hset(self, k, mapping):
        def _op(): self.store.setdefault(k, {}).update(mapping)
        getattr(self, "_ops", self.__dict__.setdefault("_ops", [])).append(_op)
    def expire(self, k, s): self.ttls[k] = s
    def hgetall(self, k): return self.store.get(k, {})


def _proc():
    return SessionProcessor(redis_client=FakeRedis(), ttl_seconds=1800)


def _evt(eid="evt_999", ts=101, item="H33", typ="click"):
    return {"event_id": eid, "session_id": "trivago:S123",
            "timestamp": ts, "item_id": item, "event_type": typ}


def test_click_updates_state_atomically():
    # Given last_ts=T / When ts=T+1 click / Then H33 + last_event + last_ts
    p = _proc()
    p.apply_event(_evt(ts=100, item="H10")); p.apply_event(_evt(eid="e2", ts=101, item="H33"))
    # Then
    st = p.get_state("trivago:S123")
    assert "H33" in st["recent_items"] and st["last_ts"] == 101
    assert p.redis.ttls["trivago:S123"] == 1800  # sliding TTL refreshed


def test_duplicate_redelivery_idempotent():
    # Given evt applied / When redelivered / Then unchanged
    p = _proc()
    p.apply_event(_evt()); before = p.get_state("trivago:S123")
    p.apply_event(_evt())
    assert p.get_state("trivago:S123") == before


def test_stale_event_ignored():
    # Given last_ts=T+5 / When ts=T+2 arrives / Then ignored
    p = _proc()
    p.apply_event(_evt(ts=105, item="H21"))
    p.apply_event(_evt(eid="stale", ts=102, item="H99"))
    st = p.get_state("trivago:S123")
    assert st["last_ts"] == 105 and "H99" not in st["recent_items"]
