"""TripRank FastAPI: POST /v1/recommend, GET /health, GET /ready, GET /metrics."""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.models.inference import score_candidates

log = logging.getLogger("triprank.api")

P95_WINDOW = 1000


class RecommendRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    track: str = "trivago"
    k: int = 20


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
    inv = inventory if inventory is not None else [f"H{i:03d}" for i in range(1, 101)]
    latencies: Deque[float] = deque(maxlen=P95_WINDOW)
    state = {"redis_ok": redis_ok, "model_ok": model_ok}

    app = FastAPI(title="TripRank", version="0.1.0")

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = request.state.request_id
        return resp

    if ranker is not None and not hasattr(ranker, "version"):
        ranker.version = model_version

    @app.post("/v1/recommend")
    def recommend(req: RecommendRequest, request: Request):
        t0 = time.perf_counter()
        rid = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        key = f"{req.track}:{req.session_id}"
        sess = store.get(key)
        elapsed_ms = lambda: (time.perf_counter() - t0) * 1000.0

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
        items, version = score_candidates(key, cands, ranker, k=req.k)
        if not items and not inv:
            return done([], version, reason="no_candidates")
        return done(items[:req.k], version)

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
