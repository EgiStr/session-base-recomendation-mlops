"""Load real RetailRocket item categories into Postgres (item_category).

Reads item_properties_part1/2.csv, keeps rows with property = 'categoryid',
latest timestamp wins per itemid, then bulk-upserts + refreshes
category_size (sibling counts). ~55% of items carry a category; the rest
stay absent — the API omits the chip rather than inventing one.

Usage:
    DATABASE_URL=postgresql://triprank:triprank@localhost:5433/triprank \\
        python scripts/db/load_item_category.py
    # schema first: psql $DATABASE_URL -f sql/04_item_category.sql
"""
from __future__ import annotations

import csv
import os
import sys

DATA_DIR = "data/raw_hf/data/RetailRocket-Recommender-Data/data"
PARTS = ["item_properties_part1.csv", "item_properties_part2.csv"]
BATCH = 50_000


def load(parts: list[str], dsn: str) -> dict:
    import psycopg

    latest: dict[int, tuple[int, str]] = {}
    scanned = 0
    for part in parts:
        path = os.path.join(DATA_DIR, part)
        if not os.path.exists(path):
            print(f"  skip missing {path}", flush=True)
            continue
        with open(path, "r", newline="") as f:
            for row in csv.DictReader(f):
                scanned += 1
                if row.get("property") != "categoryid":
                    continue
                try:
                    item = int(row["itemid"])
                    ts = int(row["timestamp"])
                    cat = row["value"].strip()
                except (TypeError, ValueError):
                    continue
                prev = latest.get(item)
                if prev is None or ts >= prev[0]:
                    latest[item] = (ts, cat)
        print(f"  ... {part}: {len(latest)} items w/ category so far", flush=True)
    print(f"CATEGORY rows kept {len(latest)} (scanned {scanned})", flush=True)

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS item_category ("
            " itemid BIGINT PRIMARY KEY, categoryid BIGINT NOT NULL,"
            " category_size INT NOT NULL DEFAULT 0, updated_ms BIGINT NOT NULL DEFAULT 0)"
        )
        with conn.cursor() as cur:
            batch: list[tuple] = []
            for item, (ts, cat) in latest.items():
                batch.append((item, int(cat), ts))
                if len(batch) >= BATCH:
                    cur.executemany(
                        "INSERT INTO item_category (itemid, categoryid, updated_ms)"
                        " VALUES (%s,%s,%s)"
                        " ON CONFLICT (itemid) DO UPDATE SET"
                        " categoryid=EXCLUDED.categoryid,"
                        " updated_ms=EXCLUDED.updated_ms",
                        batch,
                    )
                    batch = []
            if batch:
                cur.executemany(
                    "INSERT INTO item_category (itemid, categoryid, updated_ms)"
                    " VALUES (%s,%s,%s)"
                    " ON CONFLICT (itemid) DO UPDATE SET"
                    " categoryid=EXCLUDED.categoryid,"
                    " updated_ms=EXCLUDED.updated_ms",
                    batch,
                )
        conn.execute(
            "UPDATE item_category c SET category_size = s.n FROM"
            " (SELECT categoryid, count(*)::INT AS n FROM item_category"
            " GROUP BY categoryid) s WHERE c.categoryid = s.categoryid"
        )
        n = conn.execute("SELECT count(*) FROM item_category").fetchone()[0]
        ncats = conn.execute(
            "SELECT count(DISTINCT categoryid) FROM item_category").fetchone()[0]
    print(f"LOADED item_category: {n} items across {ncats} categories", flush=True)
    return {"items": n, "categories": ncats}


def main() -> None:
    dsn = os.environ.get(
        "DATABASE_URL", "postgresql://triprank:triprank@localhost:5433/triprank")
    parts = sys.argv[1:] or PARTS
    load(parts, dsn)


if __name__ == "__main__":
    main()
