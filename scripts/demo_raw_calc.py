"""Raw end-to-end calc: real Postgres rows -> 6 features -> booster -> top-5.
Session = visitor 155 prefix (7 views before first cart).
Candidates = 7 bought items + 5 seen items (12 total).
Prints every intermediate number: no black boxes.
"""
import math
import pickle

import numpy as np
import psycopg

DSN = "postgresql://triprank:triprank@localhost:5433/triprank"
PREFIX = [134620, 123027, 134620, 50928, 373637, 151670, 143373]
BOUGHT = [368372, 452082, 181405, 41882, 442601, 224623, 389974]
CANDS = BOUGHT + [143373, 151670, 373637, 50928, 134620]

with psycopg.connect(DSN) as conn:
    n = conn.execute("SELECT count(*) FROM events_raw").fetchone()[0]
    mx = conn.execute("SELECT max(views) FROM item_stats").fetchone()[0]
    rows = conn.execute(
        "SELECT itemid, views, carts, orders, item_conv_rate"
        " FROM item_stats WHERE itemid = ANY(%s)",
        [CANDS],
    ).fetchall()
stats = {r[0]: {"views": r[1], "carts": r[2], "orders": r[3],
                "conv": float(r[4] or 0.0)} for r in rows}
print(f"RAW events_raw rows: {n} | max views: {mx}")
print("RAW item_stats for our 12 candidates:")
for i in CANDS:
    s = stats[i]
    print(f"  item {i}: views={s['views']} carts={s['carts']} "
          f"orders={s['orders']} conv={s['conv']:.6f}")

bundle = pickle.load(open("artifacts/ranker-retailrocket-v1/model.pkl", "rb"))
booster = bundle["model"]
FEATS = bundle["features"]
print("\nFEATURES:", FEATS)

X, labels = [], []
for item in CANDS:
    try:
        rec = len(PREFIX) - 1 - PREFIX[::-1].index(item)
        rr = 1.0 / (len(PREFIX) - rec)
        rep = 1.0 if PREFIX.count(item) > 1 else 0.0
    except ValueError:
        rr, rep = 0.0, 0.0
    s = stats[item]
    pop = s["views"] / mx
    X.append([rr, rep, pop, s["conv"], math.log1p(len(PREFIX) + 7), pop])
    labels.append("DIBELI" if item in BOUGHT else "dilihat")

print("\nFEATURE MATRIX (raw numbers into the trees):")
for item, row, lab in zip(CANDS, X, labels):
    print(f"  {item} [{lab:7s}] " + " ".join(f"{v:.6f}" for v in row))

scores = np.asarray(booster.predict(np.array(X)))
print("\nRAW BOOSTER SCORES:")
for item, sc, lab in zip(CANDS, scores, labels):
    print(f"  {item} [{lab:7s}] score={float(sc):.6f}")

order = sorted(range(len(CANDS)), key=lambda i: (-float(scores[i]), str(CANDS[i])))
print("\nTOP-5 PREDICTION:")
for rank, i in enumerate(order[:5], 1):
    print(f"  #{rank} item {CANDS[i]} [{labels[i]}] score={float(scores[i]):.6f}")
hits = sum(1 for i in order[:5] if labels[i] == "DIBELI")
print(f"\nHITS@5 = {hits}/5 bought items in top-5")
