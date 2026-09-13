# tests/models/test_candidates.py
# Given inventory >100k items (simulated with 1200) + session S123
# When candidate generation runs / Then <=500 candidates pass to the ranker
from src.models.baseline import popularity_rank
from src.models.candidates import generate_candidates


def _inv(n, city="Bali"):
    return [{"item_id": f"H{i}", "city": city, "pop": n - i} for i in range(n)]


def _sess(**kw):
    base = {"recent_items": ["H5"], "city": "Bali", "filters": None}
    base.update(kw)
    return base


def test_retrieval_narrows_to_cap():
    # Given
    cands = generate_candidates(_sess(), _inv(1200))
    # Then
    assert len(cands) <= 500


def test_empty_segment_falls_back_to_global():
    # Given segment filter matches zero items / When runs / Then global popularity
    cands = generate_candidates(_sess(city="Nowhere"), _inv(50))
    # Then
    assert cands == popularity_rank(_inv(50), k=500)
    assert len(cands) > 0


def test_short_list_passthrough_no_padding():
    # Given retrieval yields 0<n<K / When consumed / Then exactly n items
    cands = generate_candidates(_sess(), _inv(3), k=20)
    # Then
    assert len(cands) == 3
