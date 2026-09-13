# Monitoring & Observability

> Full reference. Short-form: `docs/monitoring.md`. Sources:
> `api/main.py` (`/v1/monitor`, `/metrics`), `src/monitoring/metrics.py`,
> `src/monitoring/drift.py`, `monitoring/prometheus.yml`,
> `monitoring/grafana/dashboards/triprank.json`, compose ports.

## 1. Signal layers

| Layer | Source | Freshness |
|---|---|---|
| Serving health (P95, samples) | `GET /metrics/json` — in-process last-1000 deque | instant |
| Live traffic + drift proxy | `GET /v1/monitor` — Postgres `events_app` + `top100_overlap` | instant |
| Prometheus series | `GET /metrics` scraped every 15s (`monitoring/prometheus.yml` → `api:8000`) | ≤15 s |
| Grafana dashboard | 4 panels, 10 s refresh, last-1h window | ≤25 s end-to-end |

## 2. Metric names

`triprank_requests_total{model_version}`,
`triprank_errors_total{model_version}`,
`triprank_latency_seconds_{bucket,sum,count}{model_version}` —
observed per request in every `done()` closure, `ok=(version != "fallback")`,
so fallback serving counts as requests but errors only increment via
explicit `ok=False` paths. Today the error counter moves only when the
API marks a response not-ok; most degraded paths still return 200 with
`reason` — dashboard error-rate panels therefore under-report soft
degradation by design (hard 5xx are what they catch).

## 3. Grafana dashboard (`triprank.json`)

| Panel | Query |
|---|---|
| Requests / sec | `rate(triprank_requests_total[1m])` |
| P95 latency | `histogram_quantile(0.95, rate(triprank_latency_seconds_bucket[5m]))` |
| Error rate | `rate(triprank_errors_total[5m])` |
| P95 latency by model_version | `histogram_quantile(0.95, sum by (model_version, le) (rate(...[5m])))` |

Provisioned read-only from `monitoring/grafana/` mounts; admin/admin.
The per-version panel is the canary instrument: challenger vs champion
latency diverges there first.

## 4. Drift triggers (`src/monitoring/drift.py`)

PSI bands `<0.10` healthy / `0.10–0.25` warning / `>0.25` significant;
production NDCG drop `>5%` vs training. Either emits
`RETRAIN RECOMMENDED` with 24 h per-type debounce (`SUPPRESSED` while
debounced). The pure functions are unit-tested; the scheduled PSI pipeline
feeding them real feature distributions is **not yet wired** — `/v1/monitor`'s
`top100_overlap` is the live proxy until it is.

## 5. What to watch (operator cheatsheet)

- `top100_overlap` falling toward 0 → live taste drifted from trained
  popularity → run `retrain_from_app.py --check-only`, then cycle retrain.
- P95 climbing past 100 ms → check candidate funnel / inventory size;
  rollback threshold 200 ms.
- `ready` 503 → Redis or model bundle missing; `health` ok + `ready` 503
  isolates the dependency fast.
- Prometheus target `api:8000` down → check compose network (scrape uses
  service name `api`, not localhost).
