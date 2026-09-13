# TripRank Architecture

> Status: shipped — describes the system as built at commit `64450b6`.
> Audience: engineers onboarding to this repo, reviewers, future operators.
> All paths, env vars, ports, and behaviors below were read from the repo;
> live numbers come from the verified production state (round 163).

## 1. Big picture

TripRank is a **session-based product recommender** served over HTTP, trained
offline on the RetailRocket e-commerce log, with a closed MLOps loop:
live web traffic lands in Postgres, feeds monitoring/drift, and can trigger
retraining.

```
                    ┌─────────────────────────────────────────────┐
                    │              OFFLINE / TRAINING              │
                    │  RetailRocket CSV → Postgres (COPY stream)   │
                    │  → aggregates → LightGBM lambdarank          │
                    │  → MLflow (params/metrics/artifacts)         │
                    │  → Registry (Champion) → quality gate        │
                    └──────────────────┬──────────────────────────┘
                                       │ artifacts/ranker-retailrocket-v1/
                                       │ (model.pkl, popularity.csv,
                                       │  inventory.csv, meta.json)
                                       ▼ baked into image
┌──────┐  click/cart/order   ┌─────────────────────┐  re-ranked top-k  ┌─────┐
│ Web  │ ─────────────────▶ │   FastAPI (`api`)   │ ────────────────▶ │ Web │
│ :3001│ ◀───────────────── │   :8000             │                   └─────┘
└──────┘   reco + session    └──────┬──┬───┬───┬───┘
                                   │  │   │   │
              ┌────────────────────┘  │   │   └───────────────┐
              ▼                       ▼   ▼                   ▼
      ┌──────────────┐   ┌────────┐ ┌───────┐ ┌─────────┐ ┌───────────┐
      │ Postgres :5433│   │ Redis  │ │ Kafka │ │ MLflow  │ │Prometheus │
      │ events+aggr.  │   │sessions│ │events │ │:5000   │ │:9090      │
      └──────────────┘   └────────┘ └───┬───┘ └─────────┘ └─────┬─────┘
                                        │                     │
                               ┌────────▼────────┐            ▼
                               │ streaming svc   │   ┌──────────────┐
                               │ Kafka → Redis   │   │ Grafana :3000│
                               └─────────────────┘   │ TripRank dash│
                                                     └──────────────┘
```

Nine compose services (`docker-compose.yml`): `api`, `streaming`, `web`,
`postgres`, `redis`, `kafka`, `mlflow`, `prometheus`, `grafana`.

## 2. Design principles (enforced, not aspirational)

| Principle | Where it lives |
|---|---|
| Canonical schema: everything downstream of ingestion is dataset-agnostic | `src/data/schemas.py::CanonicalEvent`, `src/data/adapters/*` |
| No per-dataset duplicate stacks | single API path, `track`-namespaced keys (`src/data/schemas.py::namespaced_key`) |
| Timestamp authority: stale/out-of-order events are ignored | `src/streaming/session_processor.py::apply_event` (`ts < last_ts` → drop) |
| Idempotency: duplicate delivery is a no-op | `seen` set persisted per session (cap 500) |
| Atomic session writes, 30-min sliding TTL | Redis pipeline `HSET`+`EXPIRE`, `DEFAULT_TTL_SECONDS = 1800` |
| Graceful degradation: **never 5xx on model failure** | `src/models/inference.py::score_candidates` → `"fallback"`; try/except on every endpoint |
| Real data only: no invented names/prices | cards show real IDs + real stats; missing data omits the chip |
| Provenance on every run | `dataset_version` hash, `git_commit` + dirty flag on all MLflow runs |

## 3. Service catalog

| Service | Image / build | Port | Env (compose) | Role |
|---|---|---|---|---|
| `api` | `docker/Dockerfile.api` | 8000 | `MLFLOW_TRACKING_URI=http://mlflow:5000`, `REDIS_URL=redis://redis:6379/0`, `KAFKA_BOOTSTRAP_SERVERS=kafka:29092`, `DATABASE_URL=postgresql://triprank:triprank@postgres:5432/triprank` | serve reco, ingest events, monitor, metrics |
| `streaming` | `docker/Dockerfile.streaming` | — | `KAFKA_BOOTSTRAP_SERVERS=kafka:29092`, `REDIS_URL=redis://redis:6379/0` | Kafka `triprank-events` → Redis sessions |
| `web` | `docker/Dockerfile.web` (2-stage node:22) | 3001 | `NEXT_PUBLIC_API_BASE=http://localhost:8000` (browser-side, baked at build) | Next.js shop + audit + mlops + data pages |
| `postgres` | `postgres:16-alpine` | 5433→5432 | `POSTGRES_DB/USER/PASSWORD=triprank` | events + aggregates + feature store (volume `pgdata`) |
| `redis` | `redis:7-alpine` | 6379 | — | live session state |
| `kafka` | `apache/kafka:3.9.0` KRaft | 9092 | dual listeners: `INTERNAL kafka:29092` / `EXTERNAL localhost:9092` | event bus |
| `mlflow` | `python:3.12-slim` + pip mlflow | 5000 | backend `sqlite:////mlflow/mlflow.db`, artifacts `/mlflow/artifacts` (volume `mlflow-data`) | tracking + registry |
| `prometheus` | `prom/prometheus:v3.0.0` | 9090 | mount `monitoring/prometheus.yml` (scrape `api:8000`, 15s) | metrics store |
| `grafana` | `grafana/grafana:11.3.0` | 3000 | admin/admin, provisioning mounts | TripRank dashboard |

### Kafka dual-listener rationale

`kafka-python` follows broker metadata, so each client side must be
advertised an address it can reach: compose-network clients use
`kafka:29092`, host-side clients use `localhost:9092`. A single advertised
hostname breaks one side — this was a real outage, fixed in `23e0b67`.

### Web `NEXT_PUBLIC_API_BASE` subtlety

The value is **baked at `npm run build`** (Next.js inlines `NEXT_PUBLIC_*`),
so changing it requires `docker compose up -d --build web`.
`http://localhost:8000` is correct for browser-side fetches in both
local-dev and full-docker modes (via the published port).

## 4. Data stores

| Store | Contents | Source of truth for |
|---|---|---|
| Postgres `events_raw` | 2,756,101 raw events (COPY-streamed, never duplicated on disk) | training input, audit |
| Postgres `sessions` | 1,407,580 rows: `sess_len, last_ts_ms, recent_items[20]` | session aggregates |
| Postgres `item_stats` | 235,061 rows: `views, carts, orders, item_pop, item_conv_rate` | serving features, card stats |
| Postgres `item_category` | 417,053 rows: `categoryid, category_size` across 1,180 categories | category chips |
| Postgres `events_app` | live web events (`event_id PK, session_id, timestamp_ms, itemid, event, track, model_version`) | monitoring, retrain input |
| Redis `retailrocket:<sid>` | `recent_items[≤50], last_event, last_ts, seen[≤500]`, TTL 1800 sliding | live session context |
| MLflow run `e8892480` | params, 4 metrics, 3 artifacts under `model/` | model lineage |
| MLflow registry `TripRanker` | v1, alias `Champion` | deployable version |
| `artifacts/ranker-retailrocket-v1/` | `model.pkl` (346,814 B), `popularity.csv`, `inventory.csv`, `meta.json` | baked serving bundle |

## 5. Request lifecycle (warm session, happy path)

1. Browser `POST /v1/events {session_id, item_id, event_type: click}` → `api`.
2. API loads Redis state (`{track}:{sid}`), appends item (idempotent, timestamp-checked), saves back.
3. Candidates: session `recent` ∪ popularity head, funneled to ≤500.
4. `RetailRocketRanker` builds the 6-feature vector per candidate, LightGBM booster scores, top-k returned with Postgres stats + categories.
5. Response carries `request_id, session_id, model_version, latency_ms`.
6. Best-effort: same event is sunk to `events_app` (never blocks the response).
7. Prometheus observation labeled by `model_version`; Grafana panels move within ~15s.
8. Next click re-ranks: the clicked item appears top-1 (score 1.00).

## 6. Failure modes (all covered by tests or live proofs)

| Failure | Behavior | Proof |
|---|---|---|
| Ranker down / throws | `baseline-popularity` or `fallback`, still 200 | `test_degraded_parity_and_cold_session` |
| Redis down | in-process dict fallback, `ready` reports not-ready | `_resolve_store` |
| Postgres down | stats/category chips omitted, sink skipped, monitor `monitor_degraded` | `test_stats_absent_without_postgres`, `test_category_absent_without_postgres` |
| Model slow | funnel ≤500 keeps P95 ≈ 2.7ms local | P95 probe |
| Malformed Kafka message (no `timestamp`) | consumer raises `KeyError` — **known gap**, producer is our own API so low risk | noted as tech debt |
| MLflow outage at train time | promotion BLOCKED, payload queued to `/tmp/triprank-queue` | `src/registry/registry.py::promote` |

## 7. Cloud path (design only, not built)

Kafka → Pub/Sub · Redis → Memorystore · FastAPI → Cloud Run/GKE ·
MLflow → Vertex AI / MLflow on GCS · compose → GKE manifests.
UNVERIFIED: no cloud resources have been provisioned — verify by building
the migration before quoting it.
