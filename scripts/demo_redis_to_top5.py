"""Redis -> features -> booster -> top-5, all raw numbers shown.

1. GET /v1/session/demo-shop-1  (live Redis recent_items)
2. Postgres item_stats for chosen candidates (raw views/carts/orders)
3. Feature arithmetic per candidate (same formulas as _features)
4. booster.predict raw scores -> sort -> top-5
5. Compare with live API ordering.
"""
import json
import math
import pickle
import urllib.request

import numpy as np
import pandas as pd
import psycopg

BASE = "http://localhost:8000"
DSN = "postgresql://triprank:triprank@localhost:5433/triprank"


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.load(r)


sess = get("/v1/session/demo-shop-1?track=retailrocket&k=10")
recent = [str(i) for i in sess["recent_items"]]
print(f"RAW Redis recent_items ({len(recent)}): {recent}")
print("Live API top-5:", [it["item_id"] for it in sess["items"][:5]])

bundle = pickle.load(open("artifacts/ranker-retailrocket-v1/model.pkl", "rb"))
booster = bundle["model"]
pop_df = pd.read_csv("artifacts/ranker-retailrocket-v1/popularity.csv")
pop_order = pop_df["itemid"].tolist()
pop_rank = {int(v): r for r, v in enumerate(pop_order)}
pop_max = len(pop_order)
conv = {int(v): 1.0 / (r + 10) for r, v in enumerate(pop_order)}
inv_df = pd.read_csv("artifacts/ranker-retailrocket-v1/inventory.csv")
inventory = [str(v) for v in inv_df["itemid"].tolist()]
print(f"artifacts: pop={pop_max} inv={len(inventory)}")

# Same funnel as api/main.py: recent∩inv + inv head, cap 500
cands = list(dict.fromkeys([i for i in recent if i in set(inventory)] + inventory))[:500]
print(f"candidate funnel: {len(cands)} (head: {cands[:8]})")

with psycopg.connect(DSN) as conn:
    rows = conn.execute(
        "SELECT itemid, views, carts, orders FROM item_stats WHERE itemid = ANY(%s)",
        [[int(c) for c in cands[:20]]]).fetchall()
pg = {r[0]: (r[1], r[2], r[3]) for r in rows}

print("\nSTEP 1 - RAW Postgres rows (first candidates):")
for c in cands[:8]:
    print(f"  item {c}: views/carts/orders = {pg.get(int(c), 'unknown (not in item_stats)')}")

# Detailed arithmetic for 5 candidates
prefix = recent
demo = [c for c in ["546", "461686", "187946", "324", "999999"] if c in cands]
print("\nSTEP 2 - FEATURE ARITHMETIC (prefix len %d):" % len(prefix))
print("  formulas: recency=1/(P-pos) | repeat=1 if count>1 | pop=1-rank/50000")
print("            conv=1/(rank+10) | sess=log1p(P) | cand_pos=pop")
Xdemo = []
for item in demo:
    try:
        pos = len(prefix) - 1 - prefix[::-1].index(str(item))
        rr = 1.0 / (len(prefix) - pos)
        rep = 1.0 if prefix.count(str(item)) > 1 else 0.0
        where = f"last@${pos}"
    except ValueError:
        rr, rep, where = 0.0, 0.0, "absent"
    rk = pop_rank.get(int(item), pop_max)
    popv = 1.0 - rk / pop_max
    convv = float(conv.get(int(item), 0.0))
    sessv = math.log1p(len(prefix))
    print(f"  item {item} [{where}, pop_rank={rk}]:")
    print(f"    recency={rr:.4f} repeat={rep:.0f} pop={popv:.6f} "
          f"conv={convv:.6f} sess={sessv:.4f} cand_pos={popv:.6f}")
    Xdemo.append([rr, rep, popv, convv, sessv, popv])

raw = np.asarray(booster.predict(np.array(Xdemo, dtype=float)))
print("\nSTEP 3 - RAW BOOSTER SCORES (internal, only order matters):")
for item, sc in zip(demo, raw):
    print(f"  item {item}: {float(sc):.6f}")

# Full funnel scoring -> top-5
def feats(recent, candidates):
    P = [str(i) for i in recent]
    rows = []
    for item in candidates:
        try:
            pos = len(P) - 1 - P[::-1].index(str(item))
            rr = 1.0 / (len(P) - pos)
            rep = 1.0 if P.count(str(item)) > 1 else 0.0
        except ValueError:
            rr, rep = 0.0, 0.0
        pv = 1.0 - pop_rank.get(int(item), pop_max) / pop_max
        rows.append([rr, rep, pv, float(conv.get(int(item), 0.0)),
                     math.log1p(len(P)), pv])
    return np.array(rows, dtype=float)

scores = np.asarray(booster.predict(feats(recent, cands)))
order = sorted(range(len(cands)), key=lambda i: (-float(scores[i]), cands[i]))
print("\nSTEP 4 - TOP-5 FROM RAW SCORING vs LIVE API:")
live = [it["item_id"] for it in sess["items"][:5]]
for rank, i in enumerate(order[:5], 1):
    mark = "OK" if cands[i] in live else "?"
    print(f"  #{rank} item {cands[i]} raw={float(scores[i]):.4f} "
          f"display={1.0-(rank-1)*0.01:.2f} live=#{live.index(cands[i])+1 if cands[i] in live else '-'} [{mark}]")
print("live top-5:", live)
