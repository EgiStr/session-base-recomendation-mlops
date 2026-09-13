# tests/monitoring/test_drift.py
# Given PSI=0.31 / When drift runs / Then RETRAIN RECOMMENDED (debounced 24h)
from src.monitoring.drift import check_drift, check_performance_drop


def test_psi_over_threshold_fires():
    # Given significant drift / When job runs / Then trigger names feature + PSI
    out = check_drift({"hotel_price": 0.31}, store={})
    assert out["status"] == "RETRAIN RECOMMENDED" and out["psi"] == 0.31


def test_debounce_suppresses_repeat_within_24h():
    # Given same trigger fired <24h ago / When re-run / Then suppressed
    store = {}
    check_drift({"hotel_price": 0.31}, store=store, now=0)
    out = check_drift({"hotel_price": 0.31}, store=store, now=3600)
    assert out["status"] == "SUPPRESSED"


def test_ndcg_drop_fires_with_both_values():
    # Given train 0.82 vs prod 0.74 / When evaluated / Then trigger + debounce
    out = check_performance_drop(train_ndcg=0.82, prod_ndcg=0.74, store={})
    assert out["status"] == "RETRAIN RECOMMENDED" and out["prod_ndcg"] == 0.74
