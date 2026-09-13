# Monitoring

Prometheus scrapes `api:8000`; Grafana dashboard covers system (RPS, P50/P95/
P99, error rate), ML (per-version latency, prediction/drift signals), and
business proxy (CTR/conversion panels wired to event counters).

Drift: PSI bands <0.10 healthy / 0.10–0.25 warning / >0.25 significant (+ KS
secondary). Performance: production NDCG drop > 5% vs training. Either fires
RETRAIN RECOMMENDED with 24h per-type debounce.

Every response/log carries request_id, namespaced session_id, model_version,
latency_ms. `GET /health` = liveness; `GET /ready` = model + Redis readiness.
