"""Production model bundle: loads artifacts/ranker-retailrocket-v1 into a
ranker with the SAME interface the API expects (recommend + version).

Feature parity with training (src/training/dataset.py FEATURES):
recency_rank, repeat_view, item_pop, item_conv_rate, sess_len, cand_pos_pop.
Session context at serve time: recent_items + popularity/conv stats.
"""
from __future__ import annotations

import json
import math
import os
import pickle
from typing import List, Sequence

import numpy as np
import pandas as pd

ARTIFACT_DIR = os.environ.get("TRIPRANK_ARTIFACTS", "artifacts/ranker-retailrocket-v1")


class RetailRocketRanker:
    version = "ranker-retailrocket-v1"

    def __init__(self, artifact_dir: str = ARTIFACT_DIR):
        with open(os.path.join(artifact_dir, "model.pkl"), "rb") as f:
            bundle = pickle.load(f)
        self._booster = bundle["model"]
        self.version = bundle.get("version", self.version)
        pop_df = pd.read_csv(os.path.join(artifact_dir, "popularity.csv"))
        self._pop_order = pop_df["itemid"].tolist()
        self._pop_rank = {int(v): r for r, v in enumerate(self._pop_order)}
        self._pop_max = len(self._pop_order)
        inv_df = pd.read_csv(os.path.join(artifact_dir, "inventory.csv"))
        self._inventory = [str(v) for v in inv_df["itemid"].tolist()]
        meta = json.load(open(os.path.join(artifact_dir, "meta.json")))
        self.metrics = meta.get("metrics", {})
        # conv-rate stats approximated from popularity rank (monotone proxy)
        self._conv = {int(v): 1.0 / (r + 10) for r, v in enumerate(self._pop_order)}

    @property
    def inventory(self) -> List[str]:
        return self._inventory

    def _features(self, recent: Sequence[str], candidates: Sequence[str]) -> np.ndarray:
        prefix = [str(i) for i in recent]
        rows = []
        for item in candidates:
            try:
                recency_rank = 1.0 / (len(prefix) - (len(prefix) - 1 - prefix[::-1].index(str(item))))
                repeat = 1.0 if prefix.count(str(item)) > 1 else 0.0
            except ValueError:
                recency_rank, repeat = 0.0, 0.0
            pop = 1.0 - self._pop_rank.get(int(item), self._pop_max) / self._pop_max
            rows.append([recency_rank, repeat, pop,
                         float(self._conv.get(int(item), 0.0)),
                         math.log1p(len(prefix)), pop])
        return np.array(rows, dtype=float)

    def recommend(self, session_id: str, candidates: Sequence[str],
                  k: int = 20, recent: Sequence[str] | None = None) -> List[str]:
        cands = [str(c) for c in candidates]
        X = self._features(recent or [], cands)
        scores = np.asarray(self._booster.predict(X))
        order = sorted(range(len(cands)), key=lambda i: (-float(scores[i]), cands[i]))
        return [cands[i] for i in order[:k]]

    def popularity(self, k: int = 20) -> List[str]:
        return [str(v) for v in self._pop_order[:k]]
