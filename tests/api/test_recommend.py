# tests/api/test_recommend.py
# Given session with state / When POST /v1/recommend / Then <=20 ordered + version + request_id
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import api.main as main


def _client(**kw):
    store = kw.pop("store", {"trivago:S123": {"recent_items": ["H10", "H21"]}})
    ranker = MagicMock()
    ranker.recommend.side_effect = lambda sid, cands, k=20: cands[:k]
    app = main.create_app(session_store=store, ranker=ranker, **kw)
    return TestClient(app)


def test_happy_ranking_has_trace_fields():
    # Given stored session / When POST / Then ordered + model_version + request_id
    r = _client().post("/v1/recommend", json={"session_id": "S123", "track": "trivago"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 20 and body["model_version"] and body["request_id"]


def test_cold_start_unknown_session():
    # Given unknown/expired session / When POST / Then 200 baseline-popularity
    r = _client(store={}).post("/v1/recommend", json={"session_id": "S999"})
    assert r.status_code == 200 and r.json()["model_version"] == "baseline-popularity"


def test_corrupt_artifact_fallback_200():
    # Given corrupt artifact / When POST / Then 200 fallback (never 5xx)
    c = _client(model_ok=False)
    r = c.post("/v1/recommend", json={"session_id": "S123"})
    assert r.status_code == 200 and r.json()["model_version"] == "fallback"


def test_missing_session_id_422():
    # Given body {} / When POST / Then 422
    assert _client().post("/v1/recommend", json={}).status_code == 422


def test_short_and_empty_lists():
    # Given 0<n<K / When POST / Then exactly n; Given 0 everywhere / Then empty + reason
    c = _client(store={"trivago:S1": {"recent_items": []}}, inventory=["Hx"])
    assert len(c.post("/v1/recommend", json={"session_id": "S1"}).json()["items"]) == 1
    c0 = _client(store={}, inventory=[])
    r0 = c0.post("/v1/recommend", json={"session_id": "S0"})
    assert r0.json()["items"] == [] and r0.json()["reason"] == "no_candidates"


def test_health_ready_split():
    # Given Redis down / When probed / Then /health 200 + /ready 503
    c = _client(redis_ok=False)
    assert c.get("/health").status_code == 200
    assert c.get("/ready").status_code == 503
