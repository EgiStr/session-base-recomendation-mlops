"""Bulk-load RetailRocket events.csv into Postgres via COPY streaming.

Streams the CSV (never duplicates it on the 14GB disk): one COPY per
200k-row chunk, single transaction per chunk. CSV mounted read-only
at /in/events.csv inside the loader container.

Usage:
    DATABASE_URL=postgresql://triprank:triprank@localhost:5433/triprank \
        python scripts/db/load_retailrocket.py [--csv PATH] [--chunk 200000]
    # then: psql $DATABASE_URL -f sql/02_aggregates.sql
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys
import time

EVENTS_CSV = "data/raw_hf/data/RetailRocket-Recommender-Data/data/events.csv"
CHUNK = 200_000
COPY_SQL = (
    "COPY events_raw (timestamp_ms, visitorid, event, itemid, transactionid) "
    "FROM STDIN WITH (FORMAT CSV)"
)


def _chunks(fh, n: int):
    while True:
        batch = list(itertools.islice(fh, n))
        if not batch:
            return
        yield batch


def load(csv_path: str, dsn: str, chunk: int = CHUNK) -> int:
    import psycopg

    total = 0
    t0 = time.time()
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("TRUNCATE events_raw, sessions, item_stats;")
        with open(csv_path, "r", newline="") as f:
            header = f.readline()
            if "timestamp" not in header:
                raise ValueError(f"unexpected header: {header.strip()}")
            for batch in _chunks(f, chunk):
                with conn.cursor() as cur:
                    with cur.copy(COPY_SQL) as cp:
                        for line in batch:
                            cp.write(line)
                total += len(batch)
                print(f"  ... {total} rows streamed", flush=True)
    dt = time.time() - t0
    print(f"LOADED {total} rows in {dt:.1f}s", flush=True)
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=EVENTS_CSV)
    ap.add_argument("--chunk", type=int, default=CHUNK)
    ap.add_argument("--dsn", default=os.environ.get(
        "DATABASE_URL", "postgresql://triprank:triprank@localhost:5433/triprank"))
    args = ap.parse_args()
    if not os.path.exists(args.csv):
        sys.exit(f"csv not found: {args.csv}")
    load(args.csv, args.dsn, args.chunk)


if __name__ == "__main__":
    main()
