# TripRank — Real-Time Session Recommendation & MLOps Platform

Session-based product recommendation with a full MLOps lifecycle:
real-time events → session state → candidate retrieval → LightGBM ranking →
MLflow tracking/registry → gated promotion → canary rollout → drift monitoring.

- **Production track:** RetailRocket e-commerce (2.76M events / 1.41M sessions) —
  champion `ranker-retailrocket-v1`, NDCG@10 **0.9777** vs popularity 0.7274
- **Schema tracks:** Trivago RecSys 2019 + OTTO adapters (canonical, dataset-agnostic)
- Docs: [`docs/architecture.md`](docs/architecture.md) (system) ·
  [`docs/recommendation-system.md`](docs/recommendation-system.md) (recsys + features) ·
  [`docs/feature-store.md`](docs/feature-store.md) · [`docs/modeling-evaluation.md`](docs/modeling-evaluation.md) ·
  [`docs/mlops.md`](docs/mlops.md) · [`docs/api-reference.md`](docs/api-reference.md) ·
  [`docs/runbook.md`](docs/runbook.md) · [`docs/changelog.md`](docs/changelog.md)
- Spec: `docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md`

## Quickstart

```bash
pip install -r requirements.txt
docker compose up -d --build   # 9 services: api :8000, web :3001, postgres :5433,
                               # redis :6379, kafka :9092, mlflow :5000, prometheus :9090, grafana :3000
pytest -q                      # 49 passed, 2 skipped (fakes only, no live services needed)
```

Cold-start data load first (see [`docs/runbook.md`](docs/runbook.md) §2):
`01_schema.sql` → `load_retailrocket.py` → `02_aggregates.sql` →
`04_item_category.sql` → `load_item_category.py` → `03_events_app.sql`.

## API

- `POST /v1/events` — `{session_id, item_id, event_type}` → re-ranked Top-K + session (main shop path)
- `POST /v1/recommend` — `{session_id, track?}` → Top-K `{item_id, score}` + `model_version`
- `GET /v1/session/{id}` — session state + Top-K · `GET /v1/catalog?n=` — popularity head with real stats
- `GET /v1/compare?a=&b=` — manual A-vs-B stats · `GET /v1/monitor` — traffic + drift proxy
- `GET /health` — liveness; `GET /ready` — readiness (model + Redis); `GET /metrics` — Prometheus scrape
- Full reference: [`docs/api-reference.md`](docs/api-reference.md)

## Layout

```
api/            FastAPI serving (events/recommend/session/catalog/compare/monitor/health/ready/metrics)
src/
  data/         canonical schema, retailrocket/trivago/otto adapters, validation, ingestion
  features/     session feature pipeline
  models/       candidates, baselines, LightGBM ranker, production RetailRocketRanker, V4 stub, inference
  training/     train + train_real entrypoints (MLflow), dataset frame builder
  evaluation/   offline metrics + quality gate
  registry/     MLflow Registry Champion/Challenger aliases
  streaming/    kafka producer/consumer + atomic session processor
  monitoring/   drift (PSI/KS), prometheus instrumentation
  deployment/   step-gated canary + auto-rollback
sql/            01_schema, 02_aggregates, 03_events_app, 04_item_category
scripts/        db loaders (events, categories), retrain_from_app, retrain_docker
monitoring/     prometheus.yml + grafana dashboard (provisioned)
docker/         Dockerfiles (api/streaming/web)
web/            Next.js shop + mlops + data pages, audit panel
docs/           architecture, recommendation-system, feature-store, modeling-evaluation,
                mlops, api-reference, monitoring-full, runbook, data-migration,
                web-frontend, changelog (+ ml-pipeline/deployment/monitoring short-forms)
```

## Cloud path (design only, no spend)

Local Kafka → Pub/Sub · Redis → Memorystore · FastAPI → Cloud Run/GKE ·
MLflow → Vertex AI/MLflow on GCS · compose → GKE manifests.
