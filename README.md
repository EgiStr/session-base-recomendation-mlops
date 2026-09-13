# TripRank — Real-Time Session Recommendation & MLOps Platform

Session-based hotel recommendation with a full MLOps lifecycle:
real-time events → session state → candidate retrieval → LightGBM ranking →
MLflow tracking/registry → gated promotion → canary rollout → drift monitoring.

- **Primary track:** Trivago RecSys 2019 (accommodation sessions)
- **Secondary benchmark:** OTTO (scalability / generalization)
- Spec: `docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md`
- Plan: `docs/pocket/plans/2026-09-13-triprank-platform/execution-plan.md`

## Quickstart

```bash
pip install -r requirements.txt
docker compose up        # api :8000, mlflow :5000, kafka :9092, redis :6379, prometheus :9090, grafana :3000
pytest -q                # unit + integration tests (fakes only, no live services needed)
```

## API

- `POST /v1/recommend` — `{session_id, track?}` → Top-K `{item_id, score}` + `model_version`
- `GET /health` — liveness; `GET /ready` — readiness (model + Redis)
- `GET /metrics` — Prometheus scrape

## Layout

```
api/            FastAPI serving (recommend/health/ready/metrics)
src/
  data/         canonical schema, trivago/otto adapters, validation, ingestion
  features/     session feature pipeline
  models/       candidates, baselines, LightGBM ranker, V4 stub, inference
  training/     train entrypoint (MLflow)
  evaluation/   offline metrics + quality gate
  registry/     MLflow Registry Champion/Challenger aliases
  streaming/    kafka producer/consumer + atomic session processor
  monitoring/   drift (PSI/KS), prometheus instrumentation
  deployment/   step-gated canary + auto-rollback
monitoring/     prometheus.yml + grafana dashboard
docker/         Dockerfiles (api/training/streaming)
ui/             portfolio demo pages
```

## Cloud path (design only, no spend)

Local Kafka → Pub/Sub · Redis → Memorystore · FastAPI → Cloud Run/GKE ·
MLflow → Vertex AI/MLflow on GCS · compose → GKE manifests.
