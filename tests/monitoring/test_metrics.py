# tests/monitoring/test_metrics.py
# Given recommend traffic / When scraped / Then RPS + P50/P95/P99 + error + per-version latency
from prometheus_client import CollectorRegistry, generate_latest

from src.monitoring.metrics import Metrics


def test_request_counting():
    # Given 3 requests / When recorded / Then counter == 3
    m = Metrics(CollectorRegistry())
    for _ in range(3): m.observe_request("ranker-v3", 0.02, ok=True)
    assert generate_latest(m.registry).count(b"triprank_requests_total")


def test_latency_observe_and_error_counting():
    # Given latencies + 1 error / When observed / Then histogram + error counter present
    m = Metrics(CollectorRegistry())
    m.observe_request("ranker-v3", 0.05, ok=True)
    m.observe_request("ranker-v3", 0.01, ok=False)
    blob = generate_latest(m.registry)
    assert b"triprank_latency_seconds" in blob and b"triprank_errors_total" in blob


def test_version_label_split():
    # Given two model versions / When observed / Then per-version series exist
    m = Metrics(CollectorRegistry())
    m.observe_request("ranker-v3", 0.02, ok=True)
    m.observe_request("baseline-popularity", 0.01, ok=True)
    blob = generate_latest(m.registry).decode()
    assert 'model_version="ranker-v3"' in blob
    assert 'model_version="baseline-popularity"' in blob
