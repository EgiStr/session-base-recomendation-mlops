# Recommendation System

> How TripRank turns a session into a ranked list. Code refs are pinned to
> commit `64450b6`; production numbers are the shipped `ranker-retailrocket-v1`
> bundle (`artifacts/ranker-retailrocket-v1/meta.json`).

## 1. Serving pipeline (per request)

```
session state (Redis) ─┐
                       ├─▶ candidates (recent ∪ popularity, funnel ≤500)
inventory (baked CSV) ─┘          │
                                  ▼
                     RetailRocketRanker._features (6 cols)
                                  ▼
                     LightGBM booster.predict → scores
                                  ▼
                     sort (-score, item_id) → top-k
                                  ▼
                     enrich: Postgres stats + category chips
```

**Candidate funnel** (`api/main.py::ingest_event` / `get_session`): when the
inventory exceeds 500, candidates = deduped(`recent` ∩ inventory + inventory
head) capped at 500. This is what keeps full-inventory scoring (≈1.1 s) at
P95 ≈ 2.7 ms locally. Never empty when inventory exists
(`src/models/candidates.py`, `MAX_CANDIDATES = 500`).

**Scoring** (`src/models/retailrocket_ranker.py::recommend`): for each
candidate the ranker builds the same 6 features used in training
(§3 below) from live session context (`recent_items`) plus baked
popularity/conv stats, scores with the LightGBM booster, and sorts by
`(-score, item_id)` — the item-id tiebreak makes ranking deterministic.

**Graceful path** (`src/models/inference.py::score_candidates`): any failure
(no ranker, predict throws) returns `score: 0.5` popularity items with
version `"fallback"`. Cold sessions (no history) get
`baseline-popularity` with `reason: cold_start`. HTTP is always 200.

## 2. Models in play

| Model | Class | Role | Production metric |
|---|---|---|---|
| LightGBM lambdarank (`n_estimators=100, num_leaves=31, lambdarank_truncation_level=10`) | `src/models/ranker.py::LGBMRanker` (train) → `src/models/retailrocket_ranker.py::RetailRocketRanker` (serve) | Champion `ranker-retailrocket-v1` | NDCG@10 **0.9777**, Recall@20 0.9947, MRR@10 0.9727 |
| Global popularity | `src/models/baseline.py::popularity_rank` | cold-start + fallback + training baseline | NDCG@10 0.7274 |
| Item similarity | `src/models/baseline.py::item_similarity_rank` | candidate retrieval (city +2, seen −100) | — (retrieval only) |
| SessionModelProtocol (SASRec/GRU4Rec, V4) | `src/models/session_model.py` | **interface reserved, not trained** | n/a |

Train/serve parity is structural: `_features()` in the serving ranker
implements the same 6 columns as `FEATURES` in `src/training/dataset.py`,
with one documented approximation — live conv-rate is a monotone
popularity-rank proxy (`1/(rank+10)`), while training uses the true
`conv/pop` ratio. Impact: small by construction (monotone transform of an
already-present feature), and offline-online agreement is checked via the
`top100_overlap` drift proxy in `/v1/monitor`.

## 3. Feature engineering

### Training frame (`src/training/dataset.py::build_training_frame`)

Per converting session (first cart/order with prior context):

- **Context (prefix):** events before the first conversion.
- **Positives:** converted items (label **2**).
- **Candidates:** positives + up to 10 recent prefix items + popularity
  negatives (`neg_per_pos=4`, seed 42), capped at 20 per query group.
- Sessions with no conversion, or conversion at position 0, are skipped —
  the model learns *what turns a browse into a purchase*, not mere views.

### The six features (`FEATURES`)

| # | Name | Definition | Intuition |
|---|---|---|---|
| 1 | `recency_rank` | `1/(len(prefix) − recency)` of the candidate in context | last-seen items matter most |
| 2 | `repeat_view` | 1 if candidate appears >1× in prefix | re-views signal intent |
| 3 | `item_pop` | `count(item)/max_count`, train-split normalized | global demand |
| 4 | `item_conv_rate` | `(carts+orders)/views` per item | purchase efficiency |
| 5 | `sess_len` | `log1p(session length)` | engagement depth |
| 6 | `cand_pos_pop` | popularity position prior (same as `item_pop`) | retrieval-order bias correction |

Labels: graded relevance for lambdarank — non-converted candidates 0,
converted 2 (`y = 2 if item in positives else 0`). Groups = per-session
candidate counts (LightGBM `group=`).

### Live session features (`src/features/feature_engineering.py`)

`build_session_features` exposes `recent_items, city, filters, n_recent,
last_item` from canonical state, null-safe. The city/filters slots exist
because the schema supports them; RetailRocket traffic leaves them empty
(null city/device/filters is valid per the adapter contract).

## 4. Event semantics (RetailRocket → canonical)

`src/data/adapters/retailrocket.py`: `view→click` (label 0),
`addtocart→cart` (1), `transaction→order` (2), keyed
`retailrocket:<visitorid>`, timestamps ms → epoch seconds
(`src/data/schemas.py::CanonicalEvent`).

## 5. Manual verification (for humans)

- `GET /v1/catalog?n=5` → real top-5 with views/carts/orders/conv/category.
- `GET /v1/compare?a=187946&b=461686` → A-vs-B stats side by side; answers
  "why is A above B" from Postgres-grounded numbers.
- Shop page **Audit panel**: session/model/latency/request + the same
  compare tool in-UI; every number cross-checkable with the two endpoints.
