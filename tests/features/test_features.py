# tests/features/test_features.py
# Given null context / When features built / Then no raise, defaults present
from src.features.feature_engineering import build_session_features


def test_features_null_safe():
    # Given OTTO-style context-less session / When built / Then valid defaults
    feats = build_session_features({"recent_items": [], "city": None, "filters": None})
    # Then
    assert feats["recent_items"] == [] and feats["city"] is None


def test_features_keep_recent_items():
    # Given session with clicks / When built / Then recent items preserved
    feats = build_session_features({"recent_items": ["H10", "H21"], "city": "Bali", "filters": None})
    # Then
    assert feats["recent_items"] == ["H10", "H21"] and feats["city"] == "Bali"
