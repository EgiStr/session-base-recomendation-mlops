"""Real-data training set builder: sessions → per-(prefix, candidate) rows.

For each session with a converting event (cart/order), take the prefix of
events BEFORE the first conversion as context; candidates = last-N prefix
items + popularity fill; positives = converted items.
"""
from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
import pandas as pd

from src.data.adapters.retailrocket import EVENT_MAP

FEATURES = ["recency_rank", "repeat_view", "item_pop", "item_conv_rate",
            "sess_len", "cand_pos_pop"]

LABEL = {"click": 0, "cart": 1, "order": 2}


def build_training_frame(events: pd.DataFrame,
                         max_sessions: int | None = None,
                         neg_per_pos: int = 4,
                         seed: int = 42) -> Tuple[np.ndarray, np.ndarray, List[int], pd.DataFrame]:
    rng = np.random.RandomState(seed)
    events = events.sort_values(["visitorid", "timestamp"]).copy()
    events["etype"] = events["event"].map(EVENT_MAP).fillna("click")
    pop = events["itemid"].value_counts()
    conv = events[events["etype"].isin(["cart", "order"])]["itemid"].value_counts()
    conv_rate = (conv / pop).fillna(0.0).to_dict()
    pop_norm = (pop / pop.max()).to_dict()

    X_rows, y_rows, groups, meta = [], [], [], []
    sessions = events["visitorid"].unique()
    if max_sessions:
        sessions = sessions[:max_sessions]
    for vid in sessions:
        sess = events[events["visitorid"] == vid]
        items = sess["itemid"].tolist()
        etypes = sess["etype"].tolist()
        conv_idx = next((i for i, e in enumerate(etypes) if e in ("cart", "order")), None)
        if conv_idx is None or conv_idx == 0:
            continue  # need a converting event with prior context
        prefix = items[:conv_idx]
        positives = list(dict.fromkeys(
            items[i] for i, e in enumerate(etypes) if e in ("cart", "order")))
        if not prefix or not positives:
            continue
        # candidates: recent prefix items + popularity negatives
        recent = list(dict.fromkeys(reversed(prefix)))[:10]
        neg_pool = pop.index.difference(positives + prefix).tolist()
        n_neg = min(len(neg_pool), max(neg_per_pos * len(positives), 4))
        negs = list(rng.choice(neg_pool, size=n_neg, replace=False)) if n_neg else []
        cands = list(dict.fromkeys(positives + recent + negs))[:20]
        sess_len = len(sess)
        for item in cands:
            y = 2 if item in positives else 0
            try:
                recency = len(prefix) - 1 - prefix[::-1].index(item)
                recency_rank = 1.0 / (len(prefix) - recency)
                repeat = 1.0 if prefix.count(item) > 1 else 0.0
            except ValueError:
                recency_rank, repeat = 0.0, 0.0
            X_rows.append([recency_rank, repeat,
                           float(pop_norm.get(item, 0.0)),
                           float(conv_rate.get(item, 0.0)),
                           math.log1p(sess_len),
                           float(pop_norm.get(item, 0.0))])
            y_rows.append(y)
            meta.append({"visitorid": vid, "itemid": item})
        groups.append(len(cands))
    X = np.array(X_rows, dtype=float)
    y = np.array(y_rows, dtype=int)
    return X, y, groups, pd.DataFrame(meta)
