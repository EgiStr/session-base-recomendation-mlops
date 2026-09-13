"""Retrain from live traffic: events_raw + events_app → new artifact version.

MLOps cycle:
    web click/cart/order → POST /v1/events → events_app (Postgres)
    → this script rebuilds aggregates + trains + quality gate
    → artifacts/ranker-retailrocket-vN on PASS (never overwrites Champion).

Usage:
    python scripts/retrain_from_app.py [--min-app-events 100] [--out-dir artifacts/...]
    python scripts/retrain_from_app.py --check-only   # exit 0/2: enough data?
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from src.evaluation.evaluate import evaluate  # noqa: E402
from src.evaluation.quality_gate import evaluate_gate  # noqa: E402
from src.models.ranker import LGBMRanker  # noqa: E402
from src.training.dataset import FEATURES, build_training_frame  # noqa: E402
from src.training.train_real import rank_queries, split_time_holdout  # noqa: E402

DSN = os.environ.get("DATABASE_URL", "postgresql://triprank:triprank@localhost:5433/triprank")
BASE_CSV = "data/raw_hf/data/RetailRocket-Recommender-Data/data/events.csv"
EVENT_MAP = {"click": "view", "cart": "addtocart", "order": "transaction"}


def load_app_events(dsn: str) -> pd.DataFrame:
    import psycopg

    with psycopg.connect(dsn, connect_timeout=10) as conn:
        rows = conn.execute(
            "SELECT timestamp_ms, itemid, event FROM events_app ORDER BY timestamp_ms"
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["timestamp", "itemid", "event"])
    df = pd.DataFrame(rows, columns=["timestamp_ms", "itemid", "event"])
    return pd.DataFrame({
        "timestamp": df["timestamp_ms"].astype("int64"),
        "visitorid": 9_000_000_000 + (df.index.values % 50_000),
        "event": df["event"].map(EVENT_MAP).fillna("view"),
        "itemid": df["itemid"].astype("int64"),
        "transactionid": None,
    })


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-app-events", type=int, default=100)
    ap.add_argument("--sessions", type=int, default=200000)
    ap.add_argument("--holdout-days", type=int, default=7)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    app_df = load_app_events(DSN)
    n_app = len(app_df)
    print(f"app events {n_app} (min {args.min_app_events})", flush=True)
    if args.check_only:
        return {"app_events": n_app, "enough": n_app >= args.min_app_events}
    if n_app < args.min_app_events:
        raise SystemExit(f"not enough app events: {n_app} < {args.min_app_events}")

    base_df = pd.read_csv(BASE_CSV)
    df = pd.concat([base_df, app_df], ignore_index=True)
    print(f"combined rows {len(df)} (base {len(base_df)} + app {n_app})", flush=True)

    train_df, hold_df = split_time_holdout(df, args.holdout_days)
    Xtr, ytr, gtr, _ = build_training_frame(train_df, max_sessions=args.sessions)
    Xho, yho, gho, mho = build_training_frame(hold_df, max_sessions=args.sessions // 4)
    ranker = LGBMRanker(n_estimators=100, num_leaves=31,
                        lambdarank_truncation_level=10).fit(Xtr, ytr, gtr)
    pop_order = train_df["itemid"].value_counts().index.tolist()
    pop_rank = {item: r for r, item in enumerate(pop_order)}
    ranked_r, rel = rank_queries(Xho, yho, gho, mho, ranker.predict)
    rb, relb, off = {}, {}, 0
    for qi, g in enumerate(gho):
        items = mho["itemid"].iloc[off:off + g].tolist()
        order = sorted(range(g), key=lambda i: (pop_rank.get(int(items[i]), 1e9), str(items[i])))
        rb[f"q{qi}"] = [items[i] for i in order[:10]]
        relb[f"q{qi}"] = {items[i] for i in range(g) if yho[off + i] > 0}
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

    out = args.out_dir or "artifacts/ranker-retailrocket-v2"
    os.makedirs(out, exist_ok=True)
    import pickle
    with open(os.path.join(out, "model.pkl"), "wb") as f:
        pickle.dump({"model": ranker._model, "features": FEATURES,
                     "version": "ranker-retailrocket-v2"}, f)
    pd.Series(pop_order[:50000]).to_csv(os.path.join(out, "popularity.csv"),
                                        index=False, header=["itemid"])
    pd.Series(sorted(train_df["itemid"].unique().tolist())).to_csv(
        os.path.join(out, "inventory.csv"), index=False, header=["itemid"])
    meta_out = {"version": "ranker-retailrocket-v2", "app_events": n_app,
                "metrics": {k: v for k, v in m_ranker.items() if k != "seeds"},
                "baseline": {k: v for k, v in m_base.items() if k != "seeds"},
                "trained_at": int(time.time())}
    json.dump(meta_out, open(os.path.join(out, "meta.json"), "w"), indent=2)
    print("ARTIFACTS", out, flush=True)
    return meta_out


if __name__ == "__main__":
    main()
