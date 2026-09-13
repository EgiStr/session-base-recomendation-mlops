-- Item category enrichment (real RetailRocket taxonomy, not invented labels).
-- Source: item_properties_part*.csv rows where property = 'categoryid'
-- (latest timestamp wins per item). ~55% of items have a category; the rest
-- stay NULL — the API omits the chip rather than guessing.
-- Sibling counts (category_size) let a human judge "1 dari N se-kategori".
-- Standalone table on purpose: load_retailrocket.py TRUNCATEs item_stats,
-- so a column there would be wiped on every reload.

CREATE TABLE IF NOT EXISTS item_category (
  itemid        BIGINT PRIMARY KEY,
  categoryid    BIGINT NOT NULL,
  category_size INT NOT NULL DEFAULT 0,
  updated_ms    BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_item_category_cat ON item_category (categoryid);
