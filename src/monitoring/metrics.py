"""Prometheus instrumentation: RPS, latency histogram, errors — all per model_version."""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram


class Metrics:
    def __init__(self, registry: CollectorRegistry | None = None):
        self.registry = registry or CollectorRegistry()
        self.requests = Counter("triprank_requests_total", "Recommend requests",
                                ["model_version"], registry=self.registry)
        self.errors = Counter("triprank_errors_total", "Recommend errors",
                              ["model_version"], registry=self.registry)
        self.latency = Histogram("triprank_latency_seconds", "Recommend latency",
                                 ["model_version"], registry=self.registry)

    def observe_request(self, model_version: str, seconds: float, ok: bool = True) -> None:
        self.requests.labels(model_version).inc()
        self.latency.labels(model_version).observe(max(seconds, 0.0))
        if not ok:
            self.errors.labels(model_version).inc()
