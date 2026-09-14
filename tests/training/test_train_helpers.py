# tests/training/test_train_helpers.py
# Given synthetic frames / When split_time_holdout + rank_queries / Then sane splits/order
import numpy as np
import pandas as pd

from src.training.train_real import rank_queries, split_time_holdout


def _df() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [1000, 2000, 8 * 86400 * 1000 + 1000, 8 * 86400 * 1000 + 2000],
        "itemid": [1, 2, 3, 4],
    })


def test_split_time_holdout_cutoff():
    tr, ho = split_time_holdout(_df(), holdout_days=7)
    assert len(tr) == 2 and len(ho) == 2
    assert (tr["timestamp"] < ho["timestamp"].min()).all()


def test_rank_queries_orders_by_score_then_id():
    X = np.zeros((3, 6))
    y = np.array([0, 1, 0])
    meta = pd.DataFrame({"itemid": [30, 10, 20]})
    ranked, rel = rank_queries(X, y, [3], meta, scorer=lambda a: np.array([0.1, 0.9, 0.1]))
    assert ranked["q0"] == [10, 20, 30]
    assert rel["q0"] == {10}
