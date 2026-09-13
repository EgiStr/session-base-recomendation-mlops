-- App-generated events (MLOps cycle): every POST /v1/events from the web
-- lands here (best-effort) so retraining can learn from live traffic.
-- Same canonical grain as events_raw + session_id for attribution.

CREATE UNLOGGED TABLE IF NOT EXISTS events_app (
  event_id     TEXT PRIMARY KEY,
  session_id   TEXT NOT NULL,
  timestamp_ms BIGINT NOT NULL,
  itemid       BIGINT NOT NULL,
  event        TEXT NOT NULL CHECK (event IN ('click', 'cart', 'order')),
  track        TEXT NOT NULL DEFAULT 'retailrocket',
  model_version TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_app_ts ON events_app (timestamp_ms DESC);
CREATE INDEX IF NOT EXISTS idx_events_app_session ON events_app (session_id);
CREATE INDEX IF NOT EXISTS idx_events_app_item ON events_app (itemid);
