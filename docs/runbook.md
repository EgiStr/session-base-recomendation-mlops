# Runbook — Operate TripRank

> Tested commands for the full-docker stack. Working directory: repo root
> unless noted. All commands below were executed during the build sessions
> (evidence: `docs/pocket/spec/2026-09-13-triprank-platform/production-deploy-evidence.md`).

## 1. Prerequisites

- Docker Desktop running; ports free: 3001, 3000, 5000, 5433, 6379, 8000, 9090, 9092.
- Dataset CSV at `data/raw_hf/data/RetailRocket-Recommender-Data/data/`
  (`events.csv`, `item_properties_part1/2.csv`, `category_tree.csv`).
  Not in git — fetch once (auth-free, ~940MB):
  `pip install huggingface_hub && python scripts/fetch_retailrocket.py`.
  Layout verified against HF repo `DanielKiani/RetailRocket-Recommender-Data`
  (allow-pattern `data/RetailRocket-Recommender-Data/data/*.csv`).
- Python 3.12 + `pip install -r requirements.txt` (tests, retrain scripts).
- Node 22 (only for local web dev; docker path needs none).

## 2. Cold start (first ever run)

```powershell
docker compose up -d postgres            # wait healthy (~10s)
python scripts/fetch_retailrocket.py     # once: HF download ~940MB (skip if data/raw_hf present)
$env:DATABASE_URL='postgresql://triprank:triprank@localhost:5433/triprank'
psql $env:DATABASE_URL -f sql/01_schema.sql
python scripts/db/load_retailrocket.py   # COPY-stream ~2.76M rows, ~20s
psql $env:DATABASE_URL -f sql/02_aggregates.sql
psql $env:DATABASE_URL -f sql/04_item_category.sql
python scripts/db/load_item_category.py  # ~20M property rows, several minutes
psql $env:DATABASE_URL -f sql/03_events_app.sql
docker compose up -d --build             # all 9 services
```

Verify: `:8000/health` → ok; `:8000/ready` → ready; `:3001` → 200;
`GET :8000/v1/catalog?n=2` → item `187946` rank 1 with stats + category.

## 3. Daily operations

| Task | Command |
|---|---|
| Start / stop | `docker compose up -d` / `docker compose down` (volumes persist) |
| Rebuild after code change | `docker compose up -d --build api streaming web` |
| Tests + lint | `python -m pytest tests/ -q` → **49 passed, 2 skipped**; `ruff check api src tests` |
| Web typecheck (in `web/`) | `npx tsc --noEmit` |
| Retrain readiness | `python scripts/retrain_from_app.py --check-only` → `{"app_events": N, "enough": N>=100}` |
| Cycle retrain | `python scripts/retrain_from_app.py` → `artifacts/ranker-retailrocket-v2/` on gate PASS |
| Full retrain | `powershell -ExecutionPolicy Bypass -File scripts/retrain_docker.ps1` |
| Deploy new version | register → `Champion` alias → `docker compose up -d --build api` |

## 4. Failure behavior (what breaks, what keeps working)

| Failure | Symptom | Response |
|---|---|---|
| `api` container down | `:8000` refused; web shows error banner | `docker compose up -d api`; check `docker logs triple-recommendation-mlops-api-1` |
| Postgres down | monitor `reason: monitor_degraded`; cards lose stats/chips; sink skipped | reco keeps serving (200); fix DB, restart `api` to refresh lazy cache |
| Redis down | `ready` → 503; sessions fall back to in-process dict | restore Redis; per-process divergence heals with traffic |
| Kafka down | `streaming` consumer crashes/loops; API ingest unaffected (direct Redis path) | restart `kafka` then `streaming` |
| MLflow down | retrain scripts fall back to sqlite; serving unaffected (bundle baked) | restart `mlflow`; see MLflow artifact-root quirk in `docs/modeling-evaluation.md` §7 before host-side logging |
| `events_app` growing | slower `/v1/monitor` | decide retention (partition/prune/archive) — see `docs/feature-store.md` §5 |

## 5. Rollback

- **Model**: re-point registry `Champion` alias to prior version, rebuild `api` image, `up -d api`. No code change.
- **Deploy**: `docker compose up -d <service>` with the previous image — tag images before risky changes (compose has no built-in versioning).
- **Data**: aggregates rebuild idempotently (`TRUNCATE` + re-`INSERT`); raw reload is a ~20 s COPY.
