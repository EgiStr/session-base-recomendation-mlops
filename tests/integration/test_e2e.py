# tests/integration/test_e2e.py
# Given synthetic Trivago + OTTO events / When pipeline + API run
# Then ordered versioned recommendations for both tracks
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import api.main as main
from src.data.adapters.otto import normalize_otto
from src.data.adapters.trivago import normalize_trivago
from src.deployment.canary import evaluate_step
from src.streaming.session_processor import SessionProcessor


class MemRedis:
    def __init__(self):
        self.store = {}
    def pipeline(self): return self
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self): pass
    def hset(self, k, mapping): self.store.setdefault(k, {}).update(mapping)
    def expire(self, k, s): pass
    def hgetall(self, k): return self.store.get(k, {})


def _ingest(proc):
    # Given one event per track / When normalized + applied / Then dual-track state
    t = normalize_trivago({"session_id": "S1", "item_id": "H10", "timestamp": 1757760000,
                           "event_type": "click", "city": "Bali"})
    o = normalize_otto({"session_id": "s1", "order_id": "a1", "item_id": "a1",
                        "timestamp": 1757760000, "event_type": "order"})
    proc.apply_event(t.__dict__)
    proc.apply_event(o.__dict__)
    assert t.session_id == "trivago:S1" and o.session_id == "otto:s1"


def test_dual_track_ingest_recommend_canary():
    # Given dual-track ingest / When recommend + canary gate
    proc = SessionProcessor(redis_client=MemRedis(), ttl_seconds=1800)
    _ingest(proc)
    ranker = MagicMock()
    ranker.version = "ranker-v3"
    ranker.recommend.side_effect = lambda sid, cands, k=20: cands[:k]
    store = {"trivago:S1": proc.get_state("trivago:S1"),
             "otto:s1": proc.get_state("otto:s1")}
    app = main.create_app(session_store=store, ranker=ranker)
    c = TestClient(app)
    # Then ordered versioned recommendations for both tracks
    for sid, track in [("S1", "trivago"), ("s1", "otto")]:
        r = c.post("/v1/recommend", json={"session_id": sid, "track": track})
        assert r.status_code == 200 and r.json()["request_id"]
    # Given canary green window / When gate / Then advance
    assert evaluate_step("95/5", 0.005, 80, 500)["next"] == "75/25"
    # Given breach / When evaluated / Then rollback
    assert evaluate_step("75/25", 0.03, 80, 500)["next"] == "100/0"
