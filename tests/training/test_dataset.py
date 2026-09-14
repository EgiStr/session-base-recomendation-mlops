# tests/training/test_dataset.py
# Given synthetic sessions / When build_training_frame / Then X/y/groups/meta coherent
import numpy as np
import pandas as pd

from src.training.dataset import FEATURES, build_training_frame


def _events() -> pd.DataFrame:
    rows = [
        # session 1: view,view,cart (prefix 2, positive 30)
        (1, 1000, 10, None), (1, 1001, 20, None), (1, 1002, 30, None),
        # session 2: view,order
        (2, 1000, 10, None), (2, 1001, 40, "t1"),
        # session 3: no conversion → skipped
        (3, 1000, 50, None), (3, 1001, 60, None),
        # session 4: conversion first → skipped (no context)
        (4, 1000, 70, None),
    ]
    df = pd.DataFrame(rows, columns=["visitorid", "timestamp", "itemid", "transactionid"])
    df["event"] = ["view", "view", "addtocart", "view", "transaction",
                   "view", "view", "addtocart"]
    return df


def test_frame_shape_and_labels():
    X, y, groups, meta = build_training_frame(_events())
    assert X.shape[1] == len(FEATURES) == 6
    assert len(y) == len(meta) == X.shape[0] == sum(groups)
    assert set(np.unique(y)) <= {0, 2} and (y == 2).sum() >= 2
    assert len(groups) == 2  # sessions 1,2 only


def test_max_sessions_and_seed_deterministic():
    a = build_training_frame(_events(), max_sessions=1)
    b = build_training_frame(_events(), max_sessions=1)
    assert len(a[2]) == 1 and np.array_equal(a[0], b[0])


def test_needs_context_skips_first_event_conversion():
    df = pd.DataFrame([(9, 1000, 70, None)], columns=["visitorid", "timestamp", "itemid", "transactionid"])
    df["event"] = ["addtocart"]
    X, y, groups, meta = build_training_frame(df)
    assert len(groups) == 0 and X.shape[0] == 0
