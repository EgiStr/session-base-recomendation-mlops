# Architecture

Modular monolith + streaming sidecar (Option A).

```
Trivago / OTTO → adapters → canonical event → validation
  → features → candidates (≤500) → LightGBM ranker → FastAPI
  → Kafka → session processor → Redis → re-rank
  → MLflow tracking/registry → quality gate → canary → monitoring
```

Rules: downstream of the canonical schema is dataset-agnostic; no per-dataset
duplicate stacks. Track namespaces (`trivago:`/`otto:`) enforced at adapter,
Redis, and API layers. Redis writes atomic; timestamp authority for ordering;
30-min sliding TTL. Graceful degradation everywhere (never 5xx on model failure).

## Cloud path (design only)

Kafka → Pub/Sub · Redis → Memorystore · FastAPI → Cloud Run/GKE ·
MLflow → Vertex AI / MLflow on GCS · compose → GKE manifests.
