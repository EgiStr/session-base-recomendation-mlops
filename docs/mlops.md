# MLOps (Canary, Retrain Cycle, Operations)

> Deploy/drift/canary code: `src/deployment/`, `src/monitoring/`;
> registry: `src/registry/`; deploy/run docs: `docs/deployment.md`,
> `docs/monitoring.md` (short-form — this file is the full reference).

## 1. Canary ladder (`src/deployment/canary.py`)

`LADDER = 95/5 → 75/25 → 50/50 → 0/100` (champion/challenger %). Pure
`evaluate_step(current, err_rate, p95_ms, window=500)`:

- **Advance** one rung when challenger `5xx ≤ 1%` AND `P95 ≤ 100 ms` over a
  full 500-request window.
- **Rollback** to `100/0` when `5xx > 2%` OR `P95 > 200 ms` (trailing 500).
- Otherwise **hold**.

Status today: simulation-grade and deterministic — the ladder logic is
implemented and tested, but traffic splitting between two live model
versions is NOT wired into the API (single `RetailRocketRanker` serves).
UNVERIFIED: end-to-end canary with live split traffic — verify by wiring
the split before claiming canary deploys.

## 2. Data → monitoring → retrain cycle (the closed loop)

```
web click/cart/order ──POST /v1/events──▶ api ──sink──▶ events_app (Postgres)
                                                        │
                        ┌───────────────────────────────┼──────────────────┐
                        ▼                               ▼                  ▼
              /v1/monitor (traffic            retrain_from_app.py     Grafana drift
               + top100_overlap)               --check-only / run      panels
```

- **Sink** (`sink_app_event`): best-effort, never raises, dedupes on
  `event_id` conflict, maps click/cart/order back to dataset event names.
  Verified: traffic raised `events_app` 19 → 30 rows; per-row persistence
  test (`test_events_sink_persists_real_row`) plus never-blocks test.
- **Readiness gate**: `retrain_from_app.py --check-only` exits with
  `{"app_events": N, "enough": N ≥ 100}` — default threshold 100 live events.
- **Cycle run**: concatenates base CSV + mapped app rows (synthetic
  `visitorid = 9e9 + index % 50k` keeps sessions distinct), rebuilds the
  training frame, trains with identical hyperparams, evaluates, gates, and
  writes `artifacts/ranker-retailrocket-v2/` — Champion untouched, so the
  new version deploys only via explicit `promote()` + image rebuild.
- **Scheduler**: none wired yet — run manually or add a cron/CI schedule.
  UNVERIFIED: automated cadence — verify by adding the schedule job before
  promising hands-free retraining.

## 3. Drift & performance triggers (`src/monitoring/drift.py`)

| Trigger | Bands | Output | Debounce |
|---|---|---|---|
| PSI per feature | <0.10 healthy · 0.10–0.25 warning · >0.25 significant | `RETRAIN RECOMMENDED` | 24 h per type |
| Production NDCG drop | >5% vs training NDCG | `RETRAIN RECOMMENDED` (+`drop_pct`) | 24 h per type |

Live proxy available *today* without a PSI pipeline: `/v1/monitor` returns
`top100_overlap` (live click top-100 vs trained popularity head) plus
`cart_rate`/`order_rate` — a falling overlap is the early warning that
precedes a formal PSI breach.

## 4. Day-to-day operations

| Task | Command |
|---|---|
| Full stack | `docker compose up -d` (rebuild: `--build api streaming web`) |
| Health / readiness | `GET :8000/health` → `{"status":"ok"}`; `GET :8000/ready` (503 until Redis + model ready) |
| Live traffic + drift proxy | `GET :8000/v1/monitor` |
| Prometheus targets | `GET :9090/api/v1/targets` (expect `api:8000` = `up`) |
| Run tests + lint | `python -m pytest tests/ -q` (49 passed, 2 skipped) · `ruff check .` |
| Reload categories after data refresh | `psql $DATABASE_URL -f sql/04_item_category.sql` then `python scripts/db/load_item_category.py` |
| Full data reload | `python scripts/db/load_retailrocket.py` then `psql -f sql/02_aggregates.sql` (TRUNCATEs + rebuilds) |
| Rollback model | re-point `Champion` alias to prior version + rebuild api image (bundle is baked) |
| Cap Kafka disk | topic `triprank-events` auto-creates with defaults — set retention if the broker runs long |

## 5. Rollback & failure playbook

- **Bad reco quality**: `promote("TripRanker", "<prev>")` via registry, rebuild
  `api` image, `docker compose up -d api`. No code change needed.
- **Bad deploy**: `docker compose up -d <prev-image>` per service; compose has
  no versioning of its own — tag images before risky changes.
- **Postgres down**: API keeps serving (stats/chips omitted), sink skips,
  monitor degrades with `reason` — fix DB, no API restart needed (lazy-load
  retries on next process start; in-process cache means a *running* API
  won't pick up fresh aggregates until restarted).
- **Redis down**: dict fallback keeps sessions per-process; expect divergence
  across replicas — restore Redis, sessions rehydrate from traffic.
