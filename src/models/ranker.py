"""LightGBM learning-to-rank wrapper (required MVP ranker)."""
from __future__ import annotations

from typing import List, Sequence

import lightgbm as lgb
import numpy as np


class LGBMRanker:
    def __init__(self, **params):
        base = {"objective": "lambdarank", "verbosity": -1, "n_estimators": 20,
                "num_leaves": 15, "min_data_in_leaf": 1}
        base.update(params)
        self.params = base
        self._model: lgb.LGBMRanker | None = None

    def fit(self, X, y, groups: Sequence[int]) -> "LGBMRanker":
        X = np.asarray(X)
        if sum(groups) != len(X):
            raise ValueError("sum(group) must equal n_samples")
        self._model = lgb.LGBMRanker(**self.params)
        self._model.fit(X, np.asarray(y), group=list(groups))
        return self

    def predict(self, X) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("ranker not fitted")
        return np.asarray(self._model.predict(np.asarray(X)))

    @staticmethod
    def rank(ids: List[str], scores: Sequence[float], k: int = 20) -> List[str]:
        order = sorted(range(len(ids)), key=lambda i: (-float(scores[i]), str(ids[i])))
        return [ids[i] for i in order[:k]]
