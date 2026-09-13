-- RetailRocket reproduction schema.
-- Load order: 01_schema.sql then COPY events_raw then 02_aggregates.sql.

CREATE UNLOGGED TABLE IF NOT EXISTS events_raw (
  timestamp_ms BIGINT NOT NULL,
  visitorid    BIGINT NOT NULL,
  event        TEXT   NOT NULL,
  itemid       BIGINT NOT NULL,
  transactionid TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  visitorid    BIGINT PRIMARY KEY,
  sess_len     INT NOT NULL,
  last_ts_ms   BIGINT NOT NULL,
  recent_items BIGINT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS item_stats (
  itemid         BIGINT PRIMARY KEY,
  views          BIGINT NOT NULL DEFAULT 0,
  carts          BIGINT NOT NULL DEFAULT 0,
  orders         BIGINT NOT NULL DEFAULT 0,
  item_pop       DOUBLE PRECISION NOT NULL DEFAULT 0,
  item_conv_rate DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_visitor_ts ON events_raw (visitorid, timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_events_item_event ON events_raw (itemid, event);
