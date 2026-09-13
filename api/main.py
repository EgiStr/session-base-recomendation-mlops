"""TripRank FastAPI: POST /v1/recommend, POST /v1/events, GET /v1/session,
GET /health, GET /ready, GET /metrics."""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections import deque
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from pydantic import BaseModel, Field

from src.models.inference import score_candidates
from src.models.retailrocket_ranker import RetailRocketRanker
from src.monitoring.metrics import Metrics

log = logging.getLogger("triprank.api")

# Module-level Prometheus metrics on their own registry (scraped at GET /metrics).
metrics = Metrics(CollectorRegistry())

P95_WINDOW = 1000

# Item stats from Postgres (views/carts/orders/conv per itemid). Lazy-loaded,
# cached in-process, never fatal: {} when DATABASE_URL is absent/unreachable
# (tests, dev without postgres). Real data only — no synthetic fill.
_item_stats: Dict[str, Dict[str, float]] = {}
_item_stats_loaded = False
# Real RetailRocket taxonomy from sql/04_item_category (latest categoryid per
# item + sibling counts). Same lazy/never-fatal contract; items without a
# category simply carry no chip — never guessed.
_item_cats: Dict[str, Dict[str, int]] = {}
_item_cats_loaded = False


def get_item_category() -> Dict[str, Dict[str, int]]:
    """Return {item_id: {category_id, category_size}} from Postgres."""
    global _item_cats, _item_cats_loaded
    if _item_cats_loaded:
        return _item_cats
    _item_cats_loaded = True
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return _item_cats
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=5) as conn:
            rows = conn.execute(
                "SELECT itemid, categoryid, category_size FROM item_category"
            ).fetchall()
        _item_cats = {
            str(r[0]): {"category_id": int(r[1]), "category_size": int(r[2] or 0)}
            for r in rows
        }
        log.info("loaded item_category for %d items", len(_item_cats))
    except Exception as exc:
        log.warning("item_category unavailable (%s) — chips omitted", exc)
    return _item_cats


def get_item_stats() -> Dict[str, Dict[str, float]]:
    """Return {item_id: {views, carts, orders, conv_rate}} from Postgres."""
    global _item_stats, _item_stats_loaded
    if _item_stats_loaded:
        return _item_stats
    _item_stats_loaded = True
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return _item_stats
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=5) as conn:
            rows = conn.execute(
                "SELECT itemid, views, carts, orders, item_conv_rate"
                " FROM item_stats"
            ).fetchall()
        _item_stats = {
            str(r[0]): {"views": float(r[1] or 0), "carts": float(r[2] or 0),
                        "orders": float(r[3] or 0),
                        "conv_rate": float(r[4] or 0.0)}
            for r in rows
        }
        log.info("loaded item_stats for %d items", len(_item_stats))
    except Exception as exc:
        log.warning("item_stats unavailable (%s) — stats omitted", exc)
    return _item_stats


def enrich_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach real Postgres stats + real category chips to reco items.

    Unknown ids keep score only; items without a category carry no chip.
    Nothing here is invented — every field comes from Postgres aggregates
    (item_stats) or the RetailRocket taxonomy (item_category).
    """
    stats = get_item_stats()
    cats = get_item_category()
    if not stats and not cats:
        return items
    out = []
    for it in items:
        key = str(it.get("item_id"))
        st = stats.get(key)
        if st:
            it = {**it, "views": int(st["views"]), "carts": int(st["carts"]),
                  "orders": int(st["orders"]), "conv_rate": st["conv_rate"]}
        ct = cats.get(key)
        if ct:
            it = {**it, "category_id": ct["category_id"],
                  "category_size": ct["category_size"]}
        out.append(it)
    return out


def sink_app_event(ev: Any, version: str) -> None:
    """Best-effort persist of a web event to Postgres events_app (MLOps cycle).

    Never raises: missing DB / bad item id / duplicate event_id are all
    swallowed (logged at debug/warning). Response path must never block.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return
    try:
        itemid = int(ev.item_id)
    except (TypeError, ValueError):
        return
    try:
        ts_ms = int(ev.timestamp) * 1000 if int(ev.timestamp) < 10**12 else int(ev.timestamp)
    except (TypeError, ValueError):
        ts_ms = int(time.time() * 1000)
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute(
                "INSERT INTO events_app"
                " (event_id, session_id, timestamp_ms, itemid, event, track, model_version)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (event_id) DO NOTHING",
                (str(ev.event_id), str(ev.session_id), ts_ms, itemid,
                 str(ev.event_type.value), str(ev.track), str(version)),
            )
            conn.commit()
    except Exception as exc:
        log.warning("events_app sink skipped (%s)", exc)

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
    views: Optional[int] = None
    carts: Optional[int] = None
    orders: Optional[int] = None
    conv_rate: Optional[float] = None


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


def _session_exists(store: Any, key: str) -> bool:
    """True when the session key exists (even with empty history)."""
    try:
        if hasattr(store, "exists"):
            return bool(store.exists(key))
        if hasattr(store, "hgetall"):
            return bool(store.hgetall(key))
        get = getattr(store, "get", None)
        if callable(get):
            return get(key) is not None
    except Exception:
        return False
    return False


def _p95(samples: List[float]) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    idx = min(int(0.95 * len(s)), len(s) - 1)
    return s[idx]


def _resolve_store(session_store: Optional[Any],
                     redis_url: Optional[str]) -> tuple[Any, bool]:
    """Return (store, redis_ok): Redis client when reachable, else dict fallback."""
    if session_store is not None:
        return session_store, True
    url = redis_url or os.environ.get("REDIS_URL")
    if not url:
        return {}, True
    try:
        import redis as _redis

        client = _redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        log.info("connected to Redis at %s", url)
        return client, True
    except Exception as exc:
        log.warning("redis unavailable (%s) — falling back to in-process store", exc)
        return {}, False


def create_app(session_store: Optional[Dict[str, Any]] = None,
               ranker: Any = None,
               inventory: Optional[List[str]] = None,
               redis_ok: bool = True,
               model_ok: bool = True,
               model_version: str = "ranker-v1",
               redis_url: Optional[str] = None) -> FastAPI:
    store, _redis_reachable = _resolve_store(session_store, redis_url)
    redis_ok = bool(redis_ok and _redis_reachable)
    if inventory is not None:
        inv = inventory
    elif PROD_INVENTORY is not None:
        inv = PROD_INVENTORY
    else:
        inv = [f"H{i:03d}" for i in range(1, 101)]
    if ranker is None and PROD_RANKER is not None:
        ranker = PROD_RANKER
        model_version = PROD_VERSION
    elif ranker is not None and getattr(ranker, "version", None):
        try:
            model_version = str(ranker.version)
        except Exception:
            pass
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
                got = [str(i) for i in ranker.popularity(k)]
                if got:
                    return got
        except Exception:
            pass
        return [str(i) for i in inv[:k]]

    @app.post("/v1/recommend")
    def recommend(req: RecommendRequest, request: Request):
        t0 = time.perf_counter()
        rid = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        key = f"{req.track}:{req.session_id}"
        st = _get_state(store, key)

        def elapsed_ms() -> float:
            return (time.perf_counter() - t0) * 1000.0

        def done(items, version, reason=None):
            ms = elapsed_ms()
            latencies.append(ms)
            metrics.observe_request(str(version), ms / 1000.0,
                                    ok=(version != "fallback"))
            body = {"request_id": rid, "session_id": req.session_id,
                    "model_version": version, "latency_ms": round(ms, 2),
                    "items": items}
            if reason:
                body["reason"] = reason
            return body

        if not _session_exists(store, key):  # cold-start → popularity fallback
            pop = _popular(req.k)
            if not pop:
                return done([], "baseline-popularity", reason="no_candidates")
            return done(enrich_items([{"item_id": i, "score": 0.5} for i in pop]),
                        "baseline-popularity")
        if not state["model_ok"]:
            items, version = score_candidates(key, inv[:req.k], None, k=req.k)
            return done(items, "fallback")
        cands = inv[:req.k] if not st["recent_items"] else inv
        if not cands and not inv:
            return done([], model_version, reason="no_candidates")
        if not cands:
            return done([], model_version, reason="no_candidates")
        # Candidate funnel (spec: ≤500): recent session items + popularity
        # fill, so the ranker scores hundreds — never the full inventory.
        if len(cands) > 500:
            recent_set = [i for i in (st["recent_items"] or []) if i in set(cands)]
            cands = list(dict.fromkeys(recent_set + cands))[:500]
        items, version = score_candidates(key, cands, ranker, k=req.k,
                                          recent=st["recent_items"] or [])
        if not items and not inv:
            return done([], version, reason="no_candidates")
        return done(items[:req.k], version)

    @app.post("/v1/events", response_model=EventOut, response_model_exclude_none=True)
    def ingest_event(ev: EventIn, request: Request):
        """Simulation ingest: apply canonical event → state → re-rank, one round-trip."""
        t0 = time.perf_counter()
        rid = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        key = f"{ev.track}:{ev.session_id}"

        def done(items, version, recent, reason=None):
            ms = round((time.perf_counter() - t0) * 1000.0, 2)
            latencies.append(ms)
            metrics.observe_request(str(version), ms / 1000.0,
                                    ok=(version != "fallback"))
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
            out = done(enrich_items(items[:ev.k]), version, st["recent_items"][-20:])
            # MLOps cycle: persist AFTER response is built. Belt-and-suspenders:
            # sink_app_event never raises by contract, but even a monkeypatched
            # or future failure here must not touch the response path.
            try:
                sink_app_event(ev, version)
            except Exception as exc:
                log.warning("events_app sink failed (%s)", exc)
            return out
        except Exception as exc:  # never 5xx — fallback baseline
            log.error("events ingest failed: %s", exc)
            fb = [{"item_id": i, "score": 0.5} for i in _popular(ev.k)]
            return done(enrich_items(fb), "fallback", [], reason="fallback")

    @app.get("/v1/session/{session_id}", response_model=SessionOut,
             response_model_exclude_none=True)
    def get_session(session_id: str, request: Request, track: str = "retailrocket",
                    k: int = 20):
        t0 = time.perf_counter()
        rid = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        key = f"{track}:{session_id}"

        def done(items, version, recent, last_event=None, reason=None):
            ms = round((time.perf_counter() - t0) * 1000.0, 2)
            latencies.append(ms)
            metrics.observe_request(str(version), ms / 1000.0,
                                    ok=(version != "fallback"))
            return {"request_id": rid, "session_id": session_id,
                    "model_version": version, "latency_ms": ms,
                    "recent_items": recent, "items": items,
                    "last_event": last_event,
                    **({"reason": reason} if reason else {})}

        try:
            st = _get_state(store, key)
            k = max(1, min(k, 100))
            if not st["recent_items"]:
                fb = [{"item_id": i, "score": 0.5} for i in _popular(k)]
                return done(fb, "baseline-popularity", [], reason="cold_start")
            eff = ranker if state["model_ok"] else None
            cands = inv
            if len(cands) > 500:  # funnel: recent + popularity head
                recent_set = [i for i in st["recent_items"] if i in set(cands)]
                cands = list(dict.fromkeys(recent_set + cands))[:500]
            items, version = score_candidates(key, cands, eff, k=k,
                                              recent=st["recent_items"])
            return done(enrich_items(items[:k]), version, st["recent_items"][-20:],
                        last_event=st.get("last_event"))
        except Exception as exc:
            log.error("session fetch failed: %s", exc)
            fb = [{"item_id": i, "score": 0.5} for i in _popular(k)]
            return done(enrich_items(fb), "fallback", [], reason="fallback")

    @app.get("/v1/monitor")
    def monitor():
        """MLOps monitoring: live traffic (events_app) + serving health. Never 5xx."""
        body: Dict[str, Any] = {
            "model_version": model_version,
            "serving": {"p95_ms": round(_p95(list(latencies)), 2),
                        "samples": len(latencies)},
            "traffic": None,
        }
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            body["reason"] = "no_database"
            return body
        try:
            import psycopg

            with psycopg.connect(dsn, connect_timeout=5) as conn:
                total = conn.execute("SELECT count(*) FROM events_app").fetchone()[0]
                by_event = dict(conn.execute(
                    "SELECT event, count(*) FROM events_app GROUP BY event").fetchall())
                sessions = conn.execute(
                    "SELECT count(DISTINCT session_id) FROM events_app").fetchone()[0]
                last_ts = conn.execute(
                    "SELECT max(timestamp_ms) FROM events_app").fetchone()[0]
                top_now = [r[0] for r in conn.execute(
                    "SELECT itemid FROM events_app WHERE event='click'"
                    " GROUP BY itemid ORDER BY count(*) DESC LIMIT 100").fetchall()]
            clicks = int(by_event.get("click", 0) or 0)
            carts = int(by_event.get("cart", 0) or 0)
            orders = int(by_event.get("order", 0) or 0)
            # Drift proxy: overlap of live top-100 clicks vs trained popularity head.
            trained_head = set()
            try:
                if ranker is not None and hasattr(ranker, "popularity"):
                    trained_head = {int(i) for i in ranker.popularity(100)}
            except Exception:
                pass
            overlap = (len(set(top_now) & trained_head) / 100.0) if trained_head else None
            body["traffic"] = {
                "events": int(total), "sessions": int(sessions),
                "clicks": clicks, "carts": carts, "orders": orders,
                "cart_rate": round(carts / clicks, 4) if clicks else 0.0,
                "order_rate": round(orders / clicks, 4) if clicks else 0.0,
                "last_event_ms": int(last_ts) if last_ts else None,
                "top100_overlap": round(overlap, 4) if overlap is not None else None,
            }
        except Exception as exc:
            log.warning("monitor degraded (%s)", exc)
            body["traffic"] = None
            body["reason"] = "monitor_degraded"
        return body

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        if state["redis_ok"] and state["model_ok"]:
            return {"status": "ready"}
        return JSONResponse({"status": "not-ready"}, status_code=503)

    @app.get("/v1/catalog")
    def catalog(n: int = 12):
        """Popularity-ordered catalog head with real Postgres stats. Never 5xx."""
        try:
            n = max(1, min(int(n), 100))
            ids = _popular(n)
            items = enrich_items([{"item_id": str(i), "score": 0.5}
                                  for i in ids[:n]])
            return {"items": [{**it, "rank": idx + 1}
                              for idx, it in enumerate(items)]}
        except Exception as exc:
            log.error("catalog failed: %s", exc)
            return {"items": []}

    @app.get("/v1/compare")
    def compare(a: str, b: str):
        """Manual A-vs-B check: real stats + real categories side by side.

        For humans verifying a ranking decision: why is A above B (or not)?
        Every field is Postgres-grounded; unknown ids return {"known": False}.
        Never 5xx.
        """
        try:
            stats = get_item_stats()
            cats = get_item_category()

            def one(item_id: str) -> Dict[str, Any]:
                st = stats.get(str(item_id))
                ct = cats.get(str(item_id))
                if not st and not ct:
                    return {"item_id": str(item_id), "known": False}
                body: Dict[str, Any] = {"item_id": str(item_id),
                                        "known": True}
                if st:
                    body.update({"views": int(st["views"]),
                                 "carts": int(st["carts"]),
                                 "orders": int(st["orders"]),
                                 "conv_rate": st["conv_rate"]})
                if ct:
                    body.update({"category_id": ct["category_id"],
                                 "category_size": ct["category_size"]})
                return body

            return {"a": one(a), "b": one(b)}
        except Exception as exc:
            log.error("compare failed: %s", exc)
            return {"a": {"item_id": str(a), "known": False},
                    "b": {"item_id": str(b), "known": False}}

    @app.get("/metrics")
    def metrics_prom():
        return Response(generate_latest(metrics.registry),
                        media_type=CONTENT_TYPE_LATEST)

    @app.get("/metrics/json")
    def metrics_json():
        return {"p95_ms": round(_p95(list(latencies)), 2),
                "samples": len(latencies)}

    return app


app = create_app()
