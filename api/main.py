"""TripRank FastAPI: POST /v1/recommend, POST /v1/events, GET /v1/session,
GET /health, GET /ready, GET /metrics."""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.models.inference import score_candidates
from src.models.retailrocket_ranker import RetailRocketRanker

log = logging.getLogger("triprank.api")

P95_WINDOW = 1000

# Production model: baked artifact loaded once at import. Falls back to
# synthetic inventory only if artifacts are absent (dev/test path).
try:
    PROD_RANKER: Any = RetailRocketRanker()
    PROD_INVENTORY: List[str] = PROD_RANKER.inventory
    PROD_VERSION: str = PROD_RANKER.version
    log.info("loaded production ranker %s (%d items)",
             PROD_VERSION, len(PROD_INVENTORY))
except Exception as exc:  # artifacts missing (tests, dev) — lazy fallback
    log.warning("production ranker unavailable: %s", exc)
    PROD_RANKER, PROD_INVENTORY, PROD_VERSION = None, None, "ranker-v1"


class RecommendRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    track: str = "trivago"
    k: int = 20


class EventType(str, Enum):
    click = "click"
    cart = "cart"
    order = "order"


class EventIn(BaseModel):
    session_id: str = Field(..., min_length=1)
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event_type: EventType = EventType.click
    item_id: str = Field(..., min_length=1)
    timestamp: int = Field(default_factory=lambda: int(time.time()))
    track: str = "retailrocket"
    k: int = Field(default=20, ge=1, le=100)


class RecoItem(BaseModel):
    item_id: str
    score: float


class EventOut(BaseModel):
    request_id: str
    session_id: str
    model_version: str
    latency_ms: float
    items: List[RecoItem]
    recent_items: List[str]
    reason: Optional[str] = None


class SessionOut(BaseModel):
    request_id: str
    session_id: str
    model_version: str
    latency_ms: float
    recent_items: List[str]
    items: List[RecoItem]
    last_event: Optional[str] = None
    reason: Optional[str] = None


def _get_state(store: Any, key: str) -> Dict[str, Any]:
    """Read session state from dict store or Redis-hash-like client."""
    if hasattr(store, "hgetall"):
        try:
            raw = store.hgetall(key) or {}
            import json as _json

            recent = raw.get("recent_items", "[]")
            items = _json.loads(recent) if isinstance(recent, str) else list(recent)
            return {"recent_items": [str(i) for i in items],
                    "last_ts": int(raw.get("last_ts", 0) or 0),
                    "last_event": raw.get("last_event"),
                    "seen": set(_json.loads(raw.get("seen", "[]") or "[]"))}
        except Exception:
            return {"recent_items": [], "last_ts": 0, "last_event": None, "seen": set()}
    st = store.get(key) or {}
    return {"recent_items": [str(i) for i in st.get("recent_items", [])],
            "last_ts": int(st.get("last_ts", 0) or 0),
            "last_event": st.get("last_event"),
            "seen": set(st.get("seen", []))}


def _save_state(store: Any, key: str, st: Dict[str, Any]) -> None:
    if hasattr(store, "hset"):
        try:
            import json as _json

            store.hset(key, mapping={
                "recent_items": _json.dumps(st["recent_items"][-50:]),
                "last_ts": str(st["last_ts"]),
                "last_event": str(st.get("last_event") or ""),
                "seen": _json.dumps(sorted(st["seen"])[-500:])})
            if hasattr(store, "expire"):
                store.expire(key, 1800)
            return
        except Exception:
            pass
    store[key] = {"recent_items": st["recent_items"][-50:],
                  "last_ts": st["last_ts"],
                  "last_event": st.get("last_event"),
                  "seen": set(st["seen"])}


def _p95(samples: List[float]) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    idx = min(int(0.95 * len(s)), len(s) - 1)
    return s[idx]


def create_app(session_store: Optional[Dict[str, Any]] = None,
               ranker: Any = None,
               inventory: Optional[List[str]] = None,
               redis_ok: bool = True,
               model_ok: bool = True,
               model_version: str = "ranker-v1") -> FastAPI:
    store = session_store if session_store is not None else {}
    if inventory is not None:
        inv = inventory
    elif PROD_INVENTORY is not None:
        inv = PROD_INVENTORY
    else:
        inv = [f"H{i:03d}" for i in range(1, 101)]
    if ranker is None and PROD_RANKER is not None:
        ranker = PROD_RANKER
        model_version = PROD_VERSION
    latencies: Deque[float] = deque(maxlen=P95_WINDOW)
    state = {"redis_ok": redis_ok, "model_ok": model_ok and ranker is not None}

    app = FastAPI(title="TripRank", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3001", "http://web:3001"],
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "x-request-id"],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = request.state.request_id
        return resp

    if ranker is not None and not hasattr(ranker, "version"):
        ranker.version = model_version

    def _popular(k: int) -> List[str]:
        """Popularity-ordered ids: ranker.popularity when available, else inv."""
        try:
            if ranker is not None and hasattr(ranker, "popularity"):
                return [str(i) for i in ranker.popularity(k)]
        except Exception:
            pass
        return [str(i) for i in inv[:k]]

    @app.post("/v1/recommend")
    def recommend(req: RecommendRequest, request: Request):
        t0 = time.perf_counter()
        rid = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        key = f"{req.track}:{req.session_id}"
        sess = store.get(key)

        def elapsed_ms() -> float:
            return (time.perf_counter() - t0) * 1000.0

        def done(items, version, reason=None):
            ms = elapsed_ms()
            latencies.append(ms)
            body = {"request_id": rid, "session_id": req.session_id,
                    "model_version": version, "latency_ms": round(ms, 2),
                    "items": items}
            if reason:
                body["reason"] = reason
            return body

        if sess is None:  # cold-start → popularity fallback
            if not inv:
                return done([], "baseline-popularity", reason="no_candidates")
            return done([{"item_id": i, "score": 0.5} for i in inv[:req.k]],
                        "baseline-popularity")
        if not state["model_ok"]:
            items, version = score_candidates(key, inv[:req.k], None, k=req.k)
            return done(items, "fallback")
        cands = inv[:req.k] if not sess.get("recent_items") else inv
        if not cands and not inv:
            return done([], sess.get("model_version", model_version),
                        reason="no_candidates")
        if not cands:
            return done([], model_version, reason="no_candidates")
        # Candidate funnel (spec: ≤500): recent session items + popularity
        # fill, so the ranker scores hundreds — never the full inventory.
        if len(cands) > 500:
            recent_set = [i for i in (sess.get("recent_items") or []) if i in set(cands)]
            cands = list(dict.fromkeys(recent_set + cands))[:500]
        items, version = score_candidates(key, cands, ranker, k=req.k,
                                          recent=sess.get("recent_items") or [])
        if not items and not inv:
            return done([], version, reason="no_candidates")
        return done(items[:req.k], version)

    @app.post("/v1/events", response_model=EventOut)
    def ingest_event(ev: EventIn, request: Request):
        """Simulation ingest: apply canonical event → state → re-rank, one round-trip."""
        t0 = time.perf_counter()
        rid = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        key = f"{ev.track}:{ev.session_id}"

        def done(items, version, recent, reason=None):
            ms = round((time.perf_counter() - t0) * 1000.0, 2)
            latencies.append(ms)
            return {"request_id": rid, "session_id": ev.session_id,
                    "model_version": version, "latency_ms": ms,
                    "items": items, "recent_items": recent,
                    **({"reason": reason} if reason else {})}

        try:
            st = _get_state(store, key)
            if ev.event_id not in st["seen"] and ev.timestamp >= st["last_ts"]:
                st["recent_items"] = (st["recent_items"] + [ev.item_id])[-50:]
                st["last_ts"] = ev.timestamp
                st["seen"] = set(st["seen"]) | {ev.event_id}
                st["last_event"] = ev.event_type.value
                _save_state(store, key, st)
            cands = inv if st["recent_items"] else inv[:ev.k]
            if len(cands) > 500:  # funnel: recent + popularity head
                recent_set = [i for i in st["recent_items"] if i in set(cands)]
                cands = list(dict.fromkeys(recent_set + cands))[:500]
            eff = ranker if state["model_ok"] else None
            items, version = score_candidates(key, cands, eff, k=ev.k,
                                              recent=st["recent_items"])
            return done(items[:ev.k], version, st["recent_items"][-20:])
        except Exception as exc:  # never 5xx — fallback baseline
            log.error("events ingest failed: %s", exc)
            fb = [{"item_id": i, "score": 0.5} for i in inv[:ev.k]]
            return done(fb, "fallback", [], reason="fallback")

    @app.get("/v1/session/{session_id}", response_model=SessionOut)
    def get_session(session_id: str, request: Request, track: str = "retailrocket",
                    k: int = 20):
        t0 = time.perf_counter()
        rid = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        key = f"{track}:{session_id}"

        def done(items, version, recent, last_event=None, reason=None):
            ms = round((time.perf_counter() - t0) * 1000.0, 2)
            latencies.append(ms)
            return {"request_id": rid, "session_id": session_id,
                    "model_version": version, "latency_ms": ms,
                    "recent_items": recent, "items": items,
                    "last_event": last_event,
                    **({"reason": reason} if reason else {})}

        try:
            st = _get_state(store, key)
            k = max(1, min(k, 100))
            if not st["recent_items"]:
                fb = [{"item_id": i, "score": 0.5} for i in inv[:k]]
                return done(fb, "baseline-popularity", [], reason="cold_start")
            eff = ranker if state["model_ok"] else None
            cands = inv
            if len(cands) > 500:  # funnel: recent + popularity head
                recent_set = [i for i in st["recent_items"] if i in set(cands)]
                cands = list(dict.fromkeys(recent_set + cands))[:500]
            items, version = score_candidates(key, cands, eff, k=k,
                                              recent=st["recent_items"])
            return done(items[:k], version, st["recent_items"][-20:],
                        last_event=st.get("last_event"))
        except Exception as exc:
            log.error("session fetch failed: %s", exc)
            fb = [{"item_id": i, "score": 0.5} for i in inv[:k]]
            return done(fb, "fallback", [], reason="fallback")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        if state["redis_ok"] and state["model_ok"]:
            return {"status": "ready"}
        return JSONResponse({"status": "not-ready"}, status_code=503)

    @app.get("/metrics")
    def metrics():
        return {"p95_ms": round(_p95(list(latencies)), 2),
                "samples": len(latencies)}

    return app


app = create_app()
