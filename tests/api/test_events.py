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


def test_stats_absent_without_postgres():
    # Given no DATABASE_URL / When cold recommend / Then 200, items carry no stats keys
    c = _client()
    r = c.get("/v1/session/STATLESS")
    assert r.status_code == 200
    for it in r.json()["items"]:
        assert "views" not in it and "conv_rate" not in it


def test_catalog_shape_and_never_5xx():
    # Given mock ranker / When GET /v1/catalog / Then ranks 1..n, never 5xx
    c = _client()
    r = c.get("/v1/catalog?n=5")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [it["rank"] for it in items] == [1, 2, 3, 4, 5]
    assert all(it["item_id"] for it in items)


def test_category_absent_without_postgres():
    # Given no DATABASE_URL / When cold session / Then 200, items carry no category keys
    c = _client()
    r = c.get("/v1/session/NOCAT")
    assert r.status_code == 200
    for it in r.json()["items"]:
        assert "category_id" not in it and "category_size" not in it


def test_compare_shape_and_never_5xx():
    # Given mock ranker / When GET /v1/compare?a=1&b=2 / Then A/B bodies, never 5xx
    c = _client()
    r = c.get("/v1/compare?a=187946&b=461686")
    assert r.status_code == 200
    body = r.json()
    assert body["a"]["item_id"] == "187946" and body["b"]["item_id"] == "461686"
    assert "known" in body["a"] and "known" in body["b"]


def test_events_sink_never_blocks(monkeypatch):
    # Given sink raising / When POST event / Then still 200 (best-effort)
    import api.main as m

    def boom(*a, **k):
        raise RuntimeError("pg down")
    monkeypatch.setattr(m, "sink_app_event", boom)
    c = _client()
    r = c.post("/v1/events", json={"session_id": "SINK1", "item_id": "1"})
    assert r.status_code == 200 and r.json()["recent_items"] == ["1"]


def test_monitor_shape_and_never_5xx():
    # Given mock ranker / When GET /v1/monitor / Then 200 + serving block always
    c = _client()
    r = c.get("/v1/monitor")
    assert r.status_code == 200
    body = r.json()
    assert "serving" in body and "samples" in body["serving"]
    assert body["model_version"] == "ranker-test"


def test_monitor_live_traffic_with_db():
    # Given local DATABASE_URL + sunk event / When GET /v1/monitor / Then traffic counts it
    import os

    import psycopg

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        import pytest
        pytest.skip("needs local DATABASE_URL")
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
    except Exception:
        import pytest
        pytest.skip("postgres unreachable")
    c = _client()
    eid = "e-mon-live-1"
    c.post("/v1/events", json={"session_id": "MONDB", "event_id": eid,
                               "item_id": "187946", "event_type": "click"})
    try:
        body = c.get("/v1/monitor").json()
        assert body["traffic"] is not None
        assert body["traffic"]["events"] >= 1
        assert body["traffic"]["sessions"] >= 1
        assert 0.0 <= (body["traffic"]["top100_overlap"] or 0.0) <= 1.0
    finally:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute("DELETE FROM events_app WHERE event_id=%s", (eid,))
            conn.commit()


def test_events_sink_persists_real_row():    # Given local DATABASE_URL / When POST event / Then row in events_app
    import os

    import psycopg

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        import pytest
        pytest.skip("needs local DATABASE_URL")
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
    except Exception:
        import pytest
        pytest.skip("postgres unreachable")
    c = _client()
    eid = "e-sink-real-1"
    c.post("/v1/events", json={"session_id": "SINKDB", "event_id": eid,
                               "item_id": "187946", "event_type": "cart"})
    with psycopg.connect(dsn, connect_timeout=3) as conn:
        row = conn.execute(
            "SELECT session_id, itemid, event FROM events_app WHERE event_id=%s",
            (eid,)).fetchone()
    assert row == ("SINKDB", 187946, "cart")
    with psycopg.connect(dsn, connect_timeout=3) as conn:
        conn.execute("DELETE FROM events_app WHERE event_id=%s", (eid,))
        conn.commit()
