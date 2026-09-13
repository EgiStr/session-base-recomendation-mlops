# Feature Store (Postgres)

> Postgres is the offline store, the serving feature source, and the
> monitoring backend — one database, three jobs. Schema: `sql/01_schema.sql`
> (+ `sql/03_events_app.sql`, `sql/04_item_category.sql`); aggregates:
> `sql/02_aggregates.sql`. Loaders: `scripts/db/load_retailrocket.py`,
> `scripts/db/load_item_category.py`.

## 1. Tables

| Table | Grain | Key columns | Rows (verified) | Written by |
|---|---|---|---|---|
| `events_raw` | 1 raw event | `timestamp_ms, visitorid, event, itemid, transactionid` (UNLOGGED during load, then `SET LOGGED`) | 2,756,101 | `load_retailrocket.py` (COPY stream, 200k chunks, ~20 s) |
| `sessions` | 1 visitor | `visitorid PK, sess_len, last_ts_ms, recent_items[20]` | 1,407,580 | `02_aggregates.sql` |
| `item_stats` | 1 item | `itemid PK, views, carts, orders, item_pop, item_conv_rate` | 235,061 | `02_aggregates.sql` |
| `item_category` | 1 item | `itemid PK, categoryid, category_size` | 417,053 / 1,180 cats | `load_item_category.py` |
| `events_app` | 1 live web event | `event_id PK, session_id, timestamp_ms, itemid, event, track, model_version, created_at` | grows with traffic | API sink (`sink_app_event`) |

Indexes: `(visitorid, timestamp_ms)` and `(itemid, event)` on events;
`(categoryid)` on categories; `(timestamp_ms DESC, session_id, itemid)` on
app events.

## 2. How aggregates are built (`sql/02_aggregates.sql`)

- `sessions`: `GROUP BY visitorid` → count, max timestamp, last-20 itemids
  (`ARRAY_AGG ... ORDER BY timestamp_ms DESC`).
- `item_stats`: conditional counts per event type → `item_pop =
  total/max_total`, `item_conv_rate = (carts+orders)/views` (null-safe).
- `TRUNCATE` first: aggregates are fully rebuilt, never incrementally
  patched — rerunning is always safe.

## 3. How categories are built (`load_item_category.py`)

Scans `item_properties_part1/2.csv` (~20.3 M rows, streaming, no full load),
keeps `property = 'categoryid'` rows, **latest timestamp wins** per item,
bulk-upserts (50k batches), then refreshes `category_size` sibling counts.
Result: 417,053 items across 1,180 categories (~55% coverage — the rest
carry no chip, by design).

## 4. Serving contract

`api/main.py::get_item_stats` / `get_item_category`: lazy-load once per
process, cache in memory, **never fatal** — DB absent/unreachable yields
`{}` and the API serves reco without stats/chips (covered by
`test_stats_absent_without_postgres`, `test_category_absent_without_postgres`).
`enrich_items` attaches stats + category to every reco path
(events, session, catalog, fallback).

## 5. Freshness & consistency notes

- Aggregates are a **snapshot** of the CSV load; live `events_app` traffic
  does not update `item_stats` until the next retrain cycle — this is the
  documented reason `top100_overlap` in `/v1/monitor` exists (it measures
  exactly this staleness).
- `events_raw` starts UNLOGGED for load speed and is flipped LOGGED after
  `02_aggregates.sql` — crash during the ~20 s load window loses raw rows
  (reload is cheap and idempotent).
- `events_app` is UNLOGGED by design (write-heavy sink, best-effort).
  UNVERIFIED: long-term retention policy for `events_app` is undecided —
  decide (partition/prune/archive) before live traffic grows it unbounded.
