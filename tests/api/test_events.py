# tests/api/test_events.py
# Given session state / When POST /v1/events or GET /v1/session / Then 200 + trace + deterministic
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import api.main as main


def _client(**kw):
    ranker = MagicMock()
    ranker.recommend.side_effect = lambda sid, cands, k=20: cands[:k]
    ranker.version = "ranker-test"
    app = main.create_app(session_store={}, ranker=ranker,
                          inventory=["1", "2", "3", "4", "5"], **kw)
    return TestClient(app)


def test_cold_click_round_trip():
    # Given unknown sid / When POST click / Then 200 + recent + k items + trace
    c = _client()
    r = c.post("/v1/events", json={"session_id": "S1", "item_id": "1",
                                   "event_type": "click", "k": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["recent_items"] == ["1"] and len(body["items"]) == 5
    assert body["request_id"] and body["model_version"] and body["latency_ms"] >= 0


def test_idempotent_reorder():
    # Given sid [A,B] / When duplicate event_id + stale ts / Then unchanged + same items
    c = _client()
    c.post("/v1/events", json={"session_id": "S2", "event_id": "e1",
                               "item_id": "1", "timestamp": 1000})
    c.post("/v1/events", json={"session_id": "S2", "event_id": "e2",
                               "item_id": "2", "timestamp": 1001})
    before = c.get("/v1/session/S2").json()
    dup = c.post("/v1/events", json={"session_id": "S2", "event_id": "e1",
                                     "item_id": "1", "timestamp": 999}).json()
    stale = c.post("/v1/events", json={"session_id": "S2", "event_id": "e3",
                                       "item_id": "3", "timestamp": 500}).json()
    assert dup["recent_items"] == stale["recent_items"] == ["1", "2"]
    assert dup["items"] == before["items"]


def test_degraded_parity_and_cold_session():
    # Given no session / When GET / Then cold_start baseline; ranker down / Then fallback 200
    c = _client()
    r = c.get("/v1/session/NOPE")
    assert r.status_code == 200 and r.json()["reason"] == "cold_start"
    c2 = _client(model_ok=False)
    r2 = c2.post("/v1/events", json={"session_id": "S9", "item_id": "1"})
    assert r2.status_code == 200 and r2.json()["model_version"] == "fallback"
