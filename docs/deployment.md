# Deployment

One command: `docker compose up` → api :8000, mlflow :5000, kafka :9092,
redis :6379, prometheus :9090, grafana :3000.

Canary ladder 95/5 → 75/25 → 50/50 → 0/100. Each step needs a 500-request
window with challenger 5xx ≤ 1% and P95 ≤ 100ms. Rollback to 100% champion on
5xx > 2% or P95 > 200ms over trailing 500 requests. Manual fallback: re-point
the Champion alias; `docker compose up <prev>` for release rollback.

CI (`ci.yml`): ruff + pytest. Weekly/scheduled (`model-validation.yml`):
offline eval + 80% coverage gate.
