# tests/training/test_quality_gate.py
# Given champion 0.82 vs challenger 0.85 + P95 72ms + err 0.4% / When gate runs / Then PASS
from src.evaluation.quality_gate import evaluate_gate


def _m(ndcg, rec=0.6):
    return {"ndcg@10": ndcg, "recall@20": rec}


def test_gate_pass():
    # Given better challenger, healthy latency/errors / When gate / Then PASS
    assert evaluate_gate(_m(0.85), _m(0.82), p95_ms=72, err_rate=0.004)["status"] == "PASS"


def test_gate_latency_fail():
    # Given better NDCG but P95=140ms / When gate / Then FAIL, no stage change
    out = evaluate_gate(_m(0.86), _m(0.82), p95_ms=140, err_rate=0.004)
    assert out["status"] == "FAIL" and out["stage_change"] is False


def test_gate_exact_tie_passes():
    # Given exact tie / When gate / Then PASS (strict >= semantics)
    assert evaluate_gate(_m(0.82), _m(0.82), p95_ms=100, err_rate=0.01)["status"] == "PASS"
