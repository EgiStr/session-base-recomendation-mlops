# TripRanker — Production Deploy Evidence (2026-09-13)

## Model (real data)
- Dataset: RetailRocket HF `DanielKiani/RetailRocket-Recommender-Data`,
  `retailrocket-hf@2dce403bf472`, 2.756.101 events / 1.407.580 sessions / 235.061 items
- Ranker: LightGBM lambdarank, holdout last 7 days
- NDCG@10 **0.9777** vs baseline 0.7274 · Recall@20 0.9947 vs 0.9656 · MRR@10 0.9727 vs 0.6429
- Artifacts: `artifacts/ranker-retailrocket-v1/` (model.pkl, popularity.csv, inventory.csv, meta.json)

## PostgreSQL reproduction
- `docker compose up -d postgres` → healthy; `scripts/db/load_retailrocket.py` COPY-streamed
  2.756.101 rows in 20.0s; `sql/02_aggregates.sql` → sessions 1.407.580, item_stats 235.061
- Verified: top item 187946 (3410 views), counts match CSV exactly

## API (FastAPI, :8000)
- Routes: POST /v1/recommend, POST /v1/events, GET /v1/session/{id}, /health, /ready, /metrics
- Tests: **43 passed**, ruff clean (incl. tests/api/test_events.py: cold round-trip, idempotent reorder, degraded parity)
- Live: /health 200, /ready 200, POST /v1/events session livedemo1 → 200
  model_version=ranker-retailrocket-v1 + real item ids; GET /v1/session → same state

## Web (Next.js 16, :3001)
- Mobile-first, bottom tabs: `/` Belanja (Workbench) · `/mlops` (Stat-Led) · `/data` (Long Document)
- Brand: Signal Blue H252 + Cart Ember H38, Space Grotesk + Inter, ID neutral-friendly copy
- Build: `npm run build` green (/, /data, /mlops static); live :3001 → 200

## Stack (docker compose, 9 services incl. mysql eksternal)
- api:8000, web:3001, postgres:5433 (healthy, 2.76M rows), redis:6379, kafka:9092,
  mlflow:5000, prometheus:9090, grafana:3000 (+ guava-mysql eksternal)
- Images: triple-recommendation-mlops-api + -web built locally

## Browser live proof (Playwright, 2026-09-13)
- `/` shop: cold-start serves TRUE popularity (187946 #1, skor 0.500), 0 console errors
- Click "Lihat produk 187946" → sesi 1 klik → `ranker-retailrocket-v1 · 74.17ms`
- `/mlops`: API ok, Ready ready, P95 74.17ms / 26 sampel (live dari /metrics),
  NDCG@10 +25.0pp, Recall@20 +2.9pp, MRR@10 +33.0pp, gate PASS
- Fixes: CORS middleware (web:3001 ↔ api:8000), cold-start via ranker.popularity()
  (inventory.csv ascending ≠ popularity order)

## Commits
- a790c26 real-data training + production ranker · d353507 sim endpoints + brand + scaffold
- bd61b7f postgres reproduction · 6b844a3 web app · 2440000 compose web + live proof
