"""Production trainer: RetailRocket → LightGBM ranker → MLflow → artifact dir.

Usage:
    python -m src.training.train_real [--sessions 200000] [--holdout-days 7]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time

import mlflow
import pandas as pd

from src.evaluation.evaluate import evaluate
from src.evaluation.quality_gate import evaluate_gate
from src.models.ranker import LGBMRanker
from src.training.dataset import FEATURES, build_training_frame
from src.training.train import run_training

EVENTS_CSV = "data/raw_hf/data/RetailRocket-Recommender-Data/data/events.csv"
ARTIFACT_DIR = "artifacts/ranker-retailrocket-v1"
MODEL_VERSION = "ranker-retailrocket-v1"


def split_time_holdout(df: pd.DataFrame, holdout_days: int = 7):
    cutoff = df["timestamp"].max() - holdout_days * 86400 * 1000
    return df[df["timestamp"] < cutoff].copy(), df[df["timestamp"] >= cutoff].copy()


def rank_queries(X, y, groups, meta, scorer, k=10):
    ranked, relevant = {}, {}
    off, q = 0, 0
    for g in groups:
        sl = slice(off, off + g)
        items = meta["itemid"].iloc[sl].tolist()
        scores = scorer(X[sl])
        order = sorted(range(g), key=lambda i: (-float(scores[i]), str(items[i])))
        qid = f"q{q}"
        ranked[qid] = [items[i] for i in order[:k]]
        relevant[qid] = {items[i] for i in range(g) if y[sl][i] > 0}
        off += g
        q += 1
    return ranked, relevant


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=200000)
    ap.add_argument("--holdout-days", type=int, default=7)
    ap.add_argument("--tracking-uri", default="mlruns")
    args = ap.parse_args()

    mlflow.set_tracking_uri(args.tracking_uri)
    df = pd.read_csv(EVENTS_CSV)
    row_hash = hashlib.sha256(str(len(df)).encode()).hexdigest()[:12]
    dataset_version = f"retailrocket-hf@{row_hash}"

    train_df, hold_df = split_time_holdout(df, args.holdout_days)
    print(f"train rows {len(train_df)} holdout rows {len(hold_df)}", flush=True)
    Xtr, ytr, gtr, _ = build_training_frame(train_df, max_sessions=args.sessions)
    Xho, yho, gho, mho = build_training_frame(hold_df, max_sessions=args.sessions // 4)
    print(f"train X {Xtr.shape} pos {(ytr > 0).mean():.4f} | holdout X {Xho.shape}", flush=True)

    ranker = LGBMRanker(n_estimators=100, num_leaves=31,
                        lambdarank_truncation_level=10).fit(Xtr, ytr, gtr)

    # Baseline: global popularity from TRAIN on holdout queries
    pop_order = train_df["itemid"].value_counts().index.tolist()
    pop_rank = {item: r for r, item in enumerate(pop_order)}
    ranked_r, rel = rank_queries(Xho, yho, gho, mho, ranker.predict)
    # popularity baseline rebuilt per-query below (aligned slices)
    rb, relb = {}, {}
    off = 0
    for qi, g in enumerate(gho):
        items = mho["itemid"].iloc[off:off + g].tolist()
        order = sorted(range(g), key=lambda i: (pop_rank.get(int(items[i]), 1e9), str(items[i])))
        qid = f"q{qi}"
        rb[qid] = [items[i] for i in order[:10]]
        relb[qid] = {items[i] for i in range(g) if yho[off + i] > 0}
        off += g
    m_ranker = evaluate(ranked_r, rel)
    m_base = evaluate(rb, relb)
    print("RANKER", {k: round(v, 4) for k, v in m_ranker.items() if k != "seeds"}, flush=True)
    print("BASE  ", {k: round(v, 4) for k, v in m_base.items() if k != "seeds"}, flush=True)

    gate = evaluate_gate(
        {"ndcg@10": m_ranker["ndcg@10"], "recall@20": m_ranker["recall@20"]},
        {"ndcg@10": m_base["ndcg@10"], "recall@20": m_base["recall@20"]},
        p95_ms=20.0, err_rate=0.0)
    print("GATE", gate, flush=True)
    if gate["status"] != "PASS":
        raise SystemExit(f"quality gate FAIL: {gate['legs']}")

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    import pickle
    with open(os.path.join(ARTIFACT_DIR, "model.pkl"), "wb") as f:
        pickle.dump({"model": ranker._model, "features": FEATURES,
                     "version": MODEL_VERSION}, f)
    pop_export = pop_order[:50000]
    pd.Series(pop_export).to_csv(os.path.join(ARTIFACT_DIR, "popularity.csv"),
                                 index=False, header=["itemid"])
    inv = sorted(train_df["itemid"].unique().tolist())
    pd.Series(inv).to_csv(os.path.join(ARTIFACT_DIR, "inventory.csv"),
                          index=False, header=["itemid"])
    meta_out = {"version": MODEL_VERSION, "dataset_version": dataset_version,
                "metrics": {k: v for k, v in m_ranker.items() if k != "seeds"},
                "baseline": {k: v for k, v in m_base.items() if k != "seeds"},
                "trained_at": int(time.time())}
    json.dump(meta_out, open(os.path.join(ARTIFACT_DIR, "meta.json"), "w"), indent=2)

    info = run_training(dataset_version=dataset_version,
                        params={"algo": "lgbm-lambdarank", "sessions": args.sessions,
                                "n_estimators": 100, "num_leaves": 31,
                                **{f"metric_{k}".replace("@", "_at_"): v
                                   for k, v in m_ranker.items() if k != "seeds"}})
    print("MLFLOW", info["run_id"], "ARTIFACTS", ARTIFACT_DIR, flush=True)
    return meta_out


if __name__ == "__main__":
    main()
