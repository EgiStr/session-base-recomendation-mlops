# Data & Migration Notes

> Covers what the dataset is (and isn't), how it enters Postgres, and what
> changes safely vs destructively. Sources: `sql/*.sql`,
> `scripts/db/*.py`, adapter `src/data/adapters/retailrocket.py`.

## 1. The RetailRocket dataset (honest description)

RecSys Challenge 2015 e-commerce log, anonymized: **no product names,
prices, descriptions, or images exist anywhere upstream** — only numeric
`itemid`s plus hashed property values. Consequences, all user-visible:

- Cards show `Item {id}` + real stats + real `categoryid` chips; the
  "Tanpa nama — dataset hanya menyimpan ID" caption is a fact, not a bug.
- Category coverage is ~55% (417,053 / 235,061-item catalog overlap varies);
  the rest render no chip — never guessed.
- Anonymity is inherent to the source, not a loading bug. Retraining on
  more data cannot produce names.

Columns: `events.csv` = `timestamp, visitorid, event, itemid, transactionid`
(`event ∈ {view, addtocart, transaction}`); `item_properties_part*.csv` =
`timestamp, itemid, property, value` (incl. `categoryid`, `available`);
`category_tree.csv` = `categoryid, parentid` (1,669 nodes, currently
unloaded — parent traversal is future work).

Adapter mapping (`retailrocket.py`): `view→click` (label 0),
`addtocart→cart` (1), `transaction→order` (2); key
`retailrocket:<visitorid>`; ms → epoch-seconds; null city/device/filters
valid. Reverse mapping for retrain (`retrain_from_app.py::EVENT_MAP`):
`click→view, cart→addtocart, order→transaction`.

## 2. Load order (cold start)

```
01_schema.sql → COPY events_raw (load_retailrocket.py) → 02_aggregates.sql
  → 04_item_category.sql → load_item_category.py → 03_events_app.sql
```

`load_retailrocket.py` streams `events.csv` in 200k-row COPY chunks in a
single autocommit-per-chunk connection (~20 s for 2.76M rows), after
`TRUNCATE events_raw, sessions, item_stats`. **Destructive**: reloading raw
wipes aggregates — always re-run `02_aggregates.sql` after. `item_category`
is deliberately standalone so it survives raw reloads.

## 3. Safe vs destructive changes

| Change | Safety |
|---|---|
| Re-run `02_aggregates.sql` | safe (full rebuild, idempotent) |
| Re-run `load_item_category.py` | safe (upsert + recount) |
| Add a column to `item_stats` | **wiped** on next raw reload — prefer a standalone table (the `item_category` precedent) |
| `TRUNCATE events_raw` | destroys training input — reload from CSV (~20 s) |
| Drop `events_app` | loses live traffic history + retrain input — back up first |
| `events_raw` UNLOGGED→LOGGED | handled by `02_aggregates.sql` (`ALTER TABLE ... SET LOGGED`); crash mid-load loses raw rows, reload is cheap |

## 4. Scale notes

Verified at 2.76M events / 1.41M sessions / 235k items on a single laptop
Postgres: COPY ~20 s, aggregates seconds, category scan minutes (20M
property rows, streaming, constant memory). `load_retailrocket.py` never
duplicates the CSV on disk (streams from the mounted file) — relevant on
the 14 GB disk it was built on.
