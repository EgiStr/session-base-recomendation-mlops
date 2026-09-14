"""Live breakdown: fire real events at the API, show every step's numbers."""
import json
import urllib.request

BASE = "http://localhost:8000"


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def show(title, d):
    print(f"== {title} ==")
    print(f"version={d['model_version']} latency={d['latency_ms']}ms")
    print(f"recent={d['recent_items']}")
    for i, it in enumerate(d["items"][:10], 1):
        extra = []
        for k in ("views", "carts", "orders", "conv_rate", "category_id"):
            if k in it and it[k] is not None:
                extra.append(f"{k}={it[k]}")
        print(f"#{i} item={it['item_id']} score={it['score']}"
              + (f" [{', '.join(extra)}]" if extra else ""))
    if d.get("reason"):
        print("reason:", d["reason"])
    print()


show("KLIK 1: item 187946 (top populer)",
     post("/v1/events", {"session_id": "demo-shop-1", "item_id": "187946",
                         "event_type": "click", "k": 10}))
show("KLIK 2: item 461686 (populer #2)",
     post("/v1/events", {"session_id": "demo-shop-1", "item_id": "461686",
                         "event_type": "click", "k": 10}))
show("KLIK 3: item 999999 (asing, tak dikenal)",
     post("/v1/events", {"session_id": "demo-shop-1", "item_id": "999999",
                         "event_type": "click", "k": 10}))
