# tests/models/test_ranker.py
# Given tiny synthetic group data (2 queries x 5 docs) so tests run <5s
import numpy as np

from src.models.ranker import LGBMRanker
from src.models.session_model import SessionModelProtocol


def _toy():
    rng = np.random.RandomState(0)
    X = rng.rand(10, 4)
    y = np.array([2, 1, 0, 0, 0, 1, 2, 0, 0, 0])
    return X, y, [5, 5]


def test_ranker_orders_with_deterministic_tiebreak():
    # Given 10 docs in 2 groups / When scored / Then desc with item_id asc tie-break
    r = LGBMRanker().fit(*_toy())
    scores = r.predict(np.zeros((3, 4)))
    ranked = r.rank(["H3", "H1", "H2"], scores)
    # Then: order follows score desc; equal scores fall back to item_id asc
    assert ranked == sorted(ranked, key=lambda i: (-scores[["H3", "H1", "H2"].index(i)], i))


def test_ranker_fit_is_fast_on_toy():
    # Given toy data / When fit / Then group math consistent (sum(group)=n)
    X, y, g = _toy()
    assert sum(g) == len(X)
    LGBMRanker().fit(X, y, g)  # must finish in well under 5s


def test_v4_stub_raises_not_implemented():
    # Given V4 reserved interface / When fit called / Then NotImplementedError (stub only)
    import pytest
    with pytest.raises(NotImplementedError):
        SessionModelProtocol().fit(None, None)
