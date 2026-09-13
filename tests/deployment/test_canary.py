# tests/deployment/test_canary.py
# Given 95/5 green (5xx<=1%, P95<=100ms/500) / When gate / Then advance to 75/25
from src.deployment.canary import evaluate_step


def test_advance_on_green():
    # Given green window / When gate / Then next ladder step
    out = evaluate_step(current="95/5", err_rate=0.008, p95_ms=90, window=500)
    assert out["next"] == "75/25"


def test_error_breach_rolls_back():
    # Given 5xx 2.6%/trailing-500 / When evaluated / Then 100% champion
    out = evaluate_step(current="75/25", err_rate=0.026, p95_ms=80, window=500)
    assert out["next"] == "100/0" and out["challenger"] == "unhealthy"


def test_latency_breach_rolls_back():
    # Given P95>200ms / When evaluated / Then 100% champion
    out = evaluate_step(current="50/50", err_rate=0.005, p95_ms=250, window=500)
    assert out["next"] == "100/0"
