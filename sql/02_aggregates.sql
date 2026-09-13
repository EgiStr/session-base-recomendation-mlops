-- Session + item aggregates feeding ranker features.
-- sess_len -> log1p(sess_len); recent_items (DESC, cap 20) -> recency_rank/repeat_view;
-- item_pop/item_conv_rate replace in-memory popularity/conv lookups.

TRUNCATE sessions, item_stats;

INSERT INTO sessions (visitorid, sess_len, last_ts_ms, recent_items)
SELECT visitorid,
       COUNT(*)::INT,
       MAX(timestamp_ms),
       (ARRAY_AGG(itemid ORDER BY timestamp_ms DESC))[1:20]
FROM events_raw
GROUP BY visitorid;

WITH counts AS (
  SELECT itemid,
         COUNT(*) FILTER (WHERE event = 'view') AS views,
         COUNT(*) FILTER (WHERE event = 'addtocart') AS carts,
         COUNT(*) FILTER (WHERE event = 'transaction') AS orders,
         COUNT(*) AS total
  FROM events_raw
  GROUP BY itemid
),
ranked AS (
  SELECT *, MAX(total) OVER () AS max_total FROM counts
)
INSERT INTO item_stats (itemid, views, carts, orders, item_pop, item_conv_rate)
SELECT itemid, views, carts, orders,
       total::FLOAT / NULLIF(max_total, 0),
       COALESCE((carts + orders)::FLOAT / NULLIF(views, 0), 0)
FROM ranked;

ALTER TABLE events_raw SET LOGGED;
