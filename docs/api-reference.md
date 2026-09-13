# TripRank API Reference

> Source: `api/main.py` (FastAPI, `create_app`), pinned at `64450b6`.
> Base URL: `http://localhost:8000`. CORS allows `http://localhost:3001`
> and `http://web:3001`, methods GET/POST, headers `content-type, x-request-id`.
> Every response carries `X-Request-ID` (12-hex, also in body as `request_id`).
> Global contract: **never 5xx on model/data failure** — degraded answers
> carry `reason` (`cold_start`, `fallback`, `no_candidates`, `no_database`,
> `monitor_degraded`) with HTTP 200. Only `/ready` may return 503.

## Endpoints

### `POST /v1/recommend`

Stateless re-rank for a known session.

```jsonc
// request
{"session_id": "abc123", "track": "retailrocket", "k": 10}
// response 200
{"request_id": "a1b2c3d4e5f6", "session_id": "abc123",
 "model_version": "ranker-retailrocket-v1", "latency_ms": 2.71,
 "items": [{"item_id": "187946", "score": 1.0, "views": 3410, "carts": 2,
            "orders": 0, "conv_rate": 0.0006, "category_id": 1393,
            "category_size": 1296}]}
```

Cold session (unknown key) → `model_version: "baseline-popularity"`,
`score: 0.5` popularity items, no `reason` field on this path
(`recommend` cold path returns no explicit reason — the version string is
the signal). Ranker failure → `score_candidates` returns `"fallback"`.

### `POST /v1/events`

Simulation ingest: apply one canonical event → update session → re-rank,
single round-trip. Body:

```jsonc
{"session_id": "abc123", "track": "retailrocket", "item_id": "187946",
 "event_type": "click", "k": 10, "timestamp": 1726166400,
 "event_id": "optional-uuid"}
```

`event_type ∈ {click, cart, order}`. `timestamp` defaults to now (epoch s);
stale (`< last_ts`) or duplicate (`event_id` in `seen`) events leave state
untouched but still return a ranking. Response = `EventOut`: reco `items`
+ `recent_items` (last 20) + `last_event` via session fetch. Side effect:
best-effort sink to Postgres `events_app` **after** the response is built —
a sink failure only logs a warning, never touches the response.

### `GET /v1/session/{session_id}?track=retailrocket&k=20`

Read session state + current top-k (`k` clamped 1–100). Cold session →
`baseline-popularity` + `reason: "cold_start"`. Includes `last_event`.

### `GET /v1/catalog?n=12`

Popularity-ordered head (`n` clamped 1–100) with real Postgres stats,
categories, and `rank` 1..n. On any failure returns `{"items": []}` (200) —
the web falls back to its verified-real ID list via
`CatalogUnavailableError`.

### `GET /v1/compare?a=187946&b=461686`

Manual A-vs-B: Postgres-grounded stats + categories side by side.
Unknown id → `{"item_id, "known": false}`. Powers the shop Audit panel.

### `GET /v1/monitor`

```jsonc
{"model_version": "ranker-retailrocket-v1",
 "serving": {"p95_ms": 2.71, "samples": 128},
 "traffic": {"events": 30, "sessions": 5, "clicks": 20, "carts": 7,
             "orders": 3, "cart_rate": 0.35, "order_rate": 0.15,
             "last_event_ms": 1726166400000, "top100_overlap": 0.42}}
```

No `DATABASE_URL` → `"traffic": null, "reason": "no_database"`.
DB error → `"reason": "monitor_degraded"`. `top100_overlap` = live click
top-100 vs trained popularity head — the drift early-warning proxy.

### Ops endpoints

| Endpoint | Behavior |
|---|---|
| `GET /health` | `{"status": "ok"}` — liveness, no deps |
| `GET /ready` | `{"status": "ready"}` (200) or `{"status": "not-ready"}` (**503**) until Redis + model ready |
| `GET /metrics` | Prometheus text (`triprank_requests_total`, `triprank_errors_total`, `triprank_latency_seconds`, all labeled `model_version`) |
| `GET /metrics/json` | `{"p95_ms, "samples"}` from the in-process 1000-sample window — what the web `/mlops` page reads |

## Item enrichment contract

`enrich_items` attaches `views/carts/orders/conv_rate` (from `item_stats`)
and `category_id/category_size` (from `item_category`) to **every** reco
path. Unknown ids keep score only; uncategorized items carry no chip.
Postgres access is lazy-once-per-process and never fatal
(`test_stats_absent_without_postgres`,
`test_category_absent_without_postgres`).
