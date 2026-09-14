# TripRank Architecture Elaborated

> Diagrams + flows + use cases, derived from the shipped code at `fefda95`.
> Companion to `docs/architecture.md` (service catalog), `docs/api-reference.md`
> (endpoint contracts), `docs/mlops.md` (canary/retrain ops).
> Diagram notation: Mermaid. Render at https://mermaid.live or any
> Mermaid-enabled viewer. Every actor, message, and branch below traces to a
> file + line range cited inline — no invented steps.

## 0. Actor & system map

| Actor | Description | Touches |
|---|---|---|
| Shopper | Human tapping product cards in the web shop | `web/app/page.tsx` only |
| ML Engineer | Retrains, promotes, rolls back models | `scripts/*`, MLflow `:5000`, registry |
| Operator | Starts/stops stack, watches Grafana, pages on alerts | compose, `:3000`, `:9090` |
| Web (Next.js) | Shop + audit + mlops + data pages, browser-side fetches | `:3001` → API `:8000` |
| API (FastAPI) | Recommend / events / session / catalog / compare / monitor / health / ready / metrics | `api/main.py::create_app` |
| Streaming svc | Kafka `triprank-events` → `SessionProcessor` → Redis | `src/streaming/consumer.py`, `session_processor.py` |
| Redis | Live session hashes, 30-min sliding TTL | key `{track}:{session_id}` |
| Postgres | `events_raw`, `sessions`, `item_stats`, `item_category`, `events_app` | `sql/*.sql` |
| Kafka | Event bus topic `triprank-events` | dual listeners `:29092`/`:9092` |
| MLflow | Tracking runs + `TripRanker` registry (Champion/Challenger) | `:5000` |
| Prometheus/Grafana | Scrape `api:8000` every 15s; 4-panel dashboard, 10s refresh | `:9090` / `:3000` |

## 1. Use-case diagram

```mermaid
flowchart LR
    Shopper((Shopper))
    MLEngineer((ML Engineer))
    Operator((Operator))

    Shopper --> UC1[Browse catalog]
    Shopper --> UC2[Click / cart / order item]
    Shopper --> UC3[Compare A vs B]
    UC1 -.-> UC2
    UC2 --> UC4[Receive re-ranked top-K]

    MLEngineer --> UC5[Retrain from base CSV]
    MLEngineer --> UC6[Retrain from live traffic]
    MLEngineer --> UC7[Promote / rollback Champion]
    UC5 --> UC8[Quality gate PASS/FAIL]
    UC6 --> UC8

    Operator --> UC9[Start / stop stack]
    Operator --> UC10[Watch Grafana + /v1/monitor]
    Operator --> UC11[Advance / rollback canary]
    UC10 --> UC6
    UC10 --> UC11
```

Use-case notes (grounded):

- **UC1** reads `GET /v1/catalog?n=12` (`api/main.py:558`); falls back to the
  `VERIFIED_REAL` ID list when the endpoint is unavailable (`web/lib/api.ts`,
  `CatalogUnavailableError`).
- **UC2** posts `POST /v1/events` (`web/lib/api.ts::postEvent`); one round
  trip applies the event, re-ranks, and best-effort sinks to `events_app`
  (`api/main.py:411-455`).
- **UC3** calls `GET /v1/compare?a=&b=` (`api/main.py:572`); unknown ids
  return `{"known": false}` — surfaced by `AuditPanel` as the dashed
  "tak dikenal" card.
- **UC5** runs `python -m src.training.train_real` (`src/training/train_real.py:75`);
  **UC6** runs `python scripts/retrain_from_app.py` (gate at `--min-app-events 100`).
- **UC8** is `src/evaluation/quality_gate.py::evaluate_gate`: challenger NDCG/Recall
  ≥ champion, P95 ≤ 100ms, error ≤ 1%; FAIL raises `SystemExit` in `train_real.py:123`.
- **UC11** evaluates `src/deployment/canary.py::evaluate_step` over the
  `95/5 → 75/25 → 50/50 → 0/100` ladder with 500-request windows; rollback to
  `100/0` on 5xx > 2% or P95 > 200ms.

## 2. Serving sequence — `POST /v1/events` (the hot path)

One shopper tap drives this exact call chain
(`api/main.py:411-455`, `src/models/inference.py:10-28`):

```mermaid
sequenceDiagram
    actor S as Shopper
    participant W as Web :3001
    participant A as API :8000
    participant R as Redis
    participant M as Ranker (model.pkl)
    participant P as Postgres
    participant PR as Prometheus

    S->>W: tap card (click/cart/order)
    W->>A: POST /v1/events {session,item,event,k}
    A->>R: HGETALL retailrocket:{sid}
    R-->>A: recent_items, last_ts, seen
    alt duplicate event_id OR stale timestamp
        A-->>W: re-rank on unchanged state (idempotent no-op on write)
    else fresh event
        A->>R: HSET recent+last_event+last_ts + EXPIRE 1800 (pipeline)
    end
    A->>A: funnel: recent ∩ inv + inv head, cap 500
    A->>M: recommend(session, cands≤500, k, recent)
    M-->>A: ordered ids (LightGBM booster scores, tiebreak item_id)
    A->>A: score_candidates: order → 1.00/0.99/0.98 display scores
    A->>P: enrich_items: item_stats + item_category chips
    P-->>A: views/carts/orders/conv_rate/category per item
    A->>PR: observe_request(version, latency)
    A-->>W: EventOut {items, recent_items[-20:], model_version, latency_ms, request_id}
    W-->>S: re-rendered reco grid + Audit trace
    A-)P: sink_app_event → events_app (best-effort, post-response, never raises)
```

Key contracts visible in the diagram:

- Display scores (`1.00, 0.99, …`) are `1.0 − idx*0.01` from rank position
  (`inference.py:21`) — cosmetic, not booster outputs.
- `recent_items` is appended then trimmed to the last 50 in the API path
  (`api/main.py:431`) and the response carries the last 20 (`:443`);
  the streaming path caps at 50 independently (`session_processor.py:52`).
- The sink runs **after** the response object is built (`:443-449`); even a
  monkeypatched `sink_app_event` failure cannot touch the response.

## 3. Session-state flowchart (write path)

Timestamp authority + idempotency, shared by the API ingest path
(`api/main.py:429-435`) and the streaming consumer
(`session_processor.py:38-66`):

```mermaid
flowchart TD
    E[Event arrives: event_id, timestamp, item_id] --> DUP{event_id in seen?}
    DUP -- yes --> DROP1[drop: duplicate redelivery]
    DUP -- no --> STALE{timestamp < last_ts?}
    STALE -- yes --> DROP2[drop: stale out-of-order event]
    STALE -- no --> APPEND[recent = recent + item_id, cap 50]
    APPEND --> META[last_ts = ts; last_event = type; seen += event_id, cap 500]
    META --> WRITE[atomic HSET mapping + EXPIRE 1800s sliding TTL]
    WRITE --> OK[return True / re-rank downstream]

    style DROP1 fill:#f5f5f5,stroke:#999,stroke-dasharray: 4 3
    style DROP2 fill:#f5f5f5,stroke:#999,stroke-dasharray: 4 3
```

Bounds (verified constants): recent cap 50 (both writers), `seen` cap 500
(`session_processor.py:55`; API path at `api/main.py:251-260` keeps
`recent[-50:]` + `sorted(seen)[-500:]`), TTL 1800s
(`session_processor.py:8`), sliding on every accepted event.

## 4. Cold / warm / degraded serving flowchart

```mermaid
flowchart TD
    REQ[recommend / events / session request] --> KNOWN{session key exists?}
    KNOWN -- no --> COLD[baseline-popularity: top popularity, score 0.5, enriched]
    KNOWN -- yes --> MODELOK{model_ok?}
    MODELOK -- no --> FB[fallback: score 0.5 + version fallback]
    MODELOK -- yes --> FUNNEL[funnel to ≤500: recent ∩ inv + head]
    FUNNEL --> RANK[booster scores → sort -score,item_id → top-k]
    RANK --> ENRICH[enrich stats + category; unknown ids score-only]
    COLD --> RESP[200 + request_id + latency_ms + optional reason]
    FB --> RESP
    ENRICH --> RESP
    REQ -.->|any exception| SAFE[catch-all: popularity fallback, reason=fallback, still 200]

    style SAFE fill:#e8f5e9,stroke:#2e7d32
```

Only `/ready` may return 503 (Redis or model not ready, `api/main.py:552-556`).
`/health` is dependency-free (`:548-550`).

## 5. Training pipeline flowchart

`src/training/train_real.py:75-162`:

```mermaid
flowchart TD
    CSV[events.csv 2.76M rows] --> VER[dataset_version = retailrocket-hf@sha12 len]
    VER --> SPLIT[time split: cutoff = max_ts − 7d]
    SPLIT --> TR[train frame ≤200k sessions]
    SPLIT --> HO[holdout frame ≤50k sessions]
    TR --> FEAT[build_training_frame: prefix/positives/negatives → 6 feats, labels 0/2, groups]
    HO --> FEAT
    FEAT --> FIT[LGBMRanker n=100 leaves=31 lambdarank@10 .fit X,y,group]
    FIT --> RK[rank holdout queries → NDCG@10 / Recall@20 / MRR@10]
    TR --> POP[popularity baseline from TRAIN only]
    POP --> RB[rank same holdout queries by train popularity]
    RK --> GATE{gate: NDCG≥ AND Recall≥ AND P95≤100 AND err≤1%?}
    RB --> GATE
    GATE -- FAIL --> EXIT[SystemExit: never reaches registry]
    GATE -- PASS --> ART[write model.pkl + popularity.csv + inventory.csv + meta.json]
    ART --> MLF[MLflow run: params + metrics + artifacts + provenance]
    MLF --> REG[register TripRanker → alias Champion]

    style EXIT fill:#ffebee,stroke:#c62828
    style REG fill:#e8f5e9,stroke:#2e7d32
```

Provenance on every run (`src/training/train.py:21-30`): `dataset_version`,
`git_commit` + dirty flag, `run_id`. Retrain-from-traffic
(`scripts/retrain_from_app.py`) reuses `split_time_holdout`, `rank_queries`,
`build_training_frame`, and `evaluate_gate` with identical hyperparams,
mapping `events_app` rows back (`click→view, cart→addtocart, order→transaction`)
under synthetic `visitorid = 9e9 + idx % 50k`, and writes `v2` artifacts
**without touching Champion**.

## 6. Monitoring & drift loop

```mermaid
flowchart LR
    subgraph serve [Serving]
        A[API done closuresevery request]
    end
    subgraph fast [Seconds]
        B[deque 1000 latencies<br/>/metrics/json]
        C[/v1/monitor/<br/>events_app counts<br/>cart/order rates<br/>top100_overlap]
    end
    subgraph slow [15s – 10s refresh]
        D[Prometheus scrape api:8000]
        E[Grafana 4 panels<br/>rps · p95 · errors · p95 by version]
    end
    subgraph decide [Offline triggers]
        F[drift.py: PSI bands<br/>0.10 / 0.25]
        G[drift.py: NDCG drop > 5%]
        H[RETRAIN RECOMMENDED<br/>24h debounce]
    end

    A --> B
    A -->|observe_request per version| D
    D --> E
    C -->|overlap falling| F
    C -->|rates falling| G
    F --> H
    G --> H
    H -->|operator runs| I[retrain_from_app.py]
```

Metric names (`src/monitoring/metrics.py:10-15`):
`triprank_requests_total{model_version}`,
`triprank_errors_total{model_version}`,
`triprank_latency_seconds{model_version}`. Grafana queries in
`monitoring/grafana/dashboards/triprank.json:17-63`.

## 7. Deployment & rollback map

| Action | Command / call | Verified source |
|---|---|---|
| Full stack up | `docker compose up -d --build` (9 services) | `docker-compose.yml`, `docs/runbook.md` |
| Health / readiness | `GET :8000/health` → ok; `GET :8000/ready` → ready/503 | `api/main.py:548-556` |
| Deploy new version | register → move `Champion` alias → rebuild `api` (bundle baked) | `registry.py:26-28`, `docs/mlops.md` §5 |
| Rollback model | re-point `Champion` to prior version + rebuild `api` | `docs/runbook.md` §5 |
| Rollback deploy | `docker compose up -d <service>` with previous image (tag first — compose has no versioning) | `docs/runbook.md` §5 |
| Canary advance | `evaluate_step`: err ≤ 1% + p95 ≤ 100ms over 500 req → next rung | `canary.py:18-24` |
| Canary rollback | err > 2% or p95 > 200ms → `100/0` | `canary.py:14-17` |
| Registry outage | `promote()` returns BLOCKED + queues JSON to `/tmp/triprank-queue` | `registry.py:31-39` |

UNVERIFIED: end-to-end canary with live split traffic (ladder logic is
implemented + tested; the API serves a single ranker — verify by wiring the
split before claiming canary deploys). UNVERIFIED: automated retrain cadence
(no scheduler wired — run manually or add cron/CI).
