# tests/evaluation/test_metrics.py
# Given finished evaluation / When inspected / Then 3-seed means recorded
from src.evaluation.evaluate import compare, evaluate


def test_evaluate_records_seeded_means():
    # Given trivial ranked vs relevant / When evaluated / Then seeds [42,7,123] recorded
    res = evaluate({"q1": ["H1", "H2", "H3"]}, {"q1": {"H2"}}, k=10)
    # Then
    assert res["seeds"] == [42, 7, 123]
    assert {"ndcg@10", "recall@20", "mrr@10"} <= set(res)


def test_compare_blocked_without_baseline():
    # Given no baseline metrics / When challenger claims improvement / Then BLOCKED
    out = compare({"ndcg@10": 0.9}, None)
    # Then
    assert out["status"] == "BLOCKED"
