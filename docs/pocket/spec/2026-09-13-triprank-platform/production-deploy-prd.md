# TripRank — Production Deployment PRD Addendum

**Date:** 2026-09-13
**Status:** approved
**Parent spec:** docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
**Goal:** production-ready local deployment trained on REAL data, served live.

---

## 1. Objective

Take TripRank from synthetic-tested MVP to a production-style deployment:

```
REAL dataset → train → MLflow → quality gate → bake model into API image
→ docker compose up → live /v1/recommend served by the REAL trained ranker
```

## 2. Dataset Decision (locked 2026-09-13)

| Track | Dataset | Status |
|-------|---------|--------|
| Real training data | **RetailRocket e-commerce** (~2.7M events, HF `DanielKiani/RetailRocket-Recommender-Data`, auth-free) | **APPROVED — in progress** |
| Primary hotel story | Trivago RecSys 2019 mirror (Kaggle) | BLOCKED on user Kaggle creds; adapter + interface already exist |
| Secondary benchmark | OTTO | interface exists; deferred |

Event mapping (RetailRocket → canonical): `view` → click (label 0),
`addtocart` → cart (label 1), `transaction` → order (label 2). Track id:
`retailrocket`. Null city/device/filters are valid per H1.

Domain note: items are products, not hotels. Serving copy says
"item recommendations"; hotel-domain story resumes when Trivago lands.
No code fork — same canonical schema, same pipeline.

## 3. Training Protocol (real data)

1. Download `events.csv` (+ `category_tree.csv`, `item_properties` optional) to `data/raw/`.
2. Build sessions: group by `visitorid`, sort by timestamp; label per event type.
3. Per-session query groups: last event = positive (label>0) when present else
   all-view sessions used for candidate/popularity stats only.
4. Features per (session-prefix, candidate): recency rank, repeat-view flag,
   item global popularity, item cart/order rate, session length, position bias.
5. `LGBMRanker` lambdarank, groups = session query sizes; eval on time-split
   holdout (last 7 days of events).
6. Metrics: Recall@10/20, NDCG@10, MRR@10 on holdout + V1 popularity baseline
   on the SAME split (baseline-first gate).
7. Log to MLflow: params, metrics, artifacts (model.pkl, feature schema,
   dataset_version = HF revision + row hash, git_commit). Save model to
   `artifacts/ranker-retailrocket-v1/` for Docker bake-in.

Success bar: ranker beats popularity baseline on NDCG@10 on the holdout.
Latency bar unchanged: P95 ≤ 100ms edge.

## 4. Deployment Protocol

1. `docker build -f docker/Dockerfile.api -t triprank-api:prod .` — image
   MUST contain `artifacts/ranker-retailrocket-v1/` and load it at startup
   (no synthetic fallback as primary path; fallback stays for failure only).
2. API startup: load real ranker + real item inventory from training stats;
   `/ready` 503 until model loaded; `/health` liveness only.
3. `docker compose up -d` full stack (api, mlflow, kafka, redis, prometheus,
   grafana). redis:7-alpine, apache/kafka:3.9.0, prom/prometheus:v3.0.0,
   grafana/grafana:11.3.0 — already pinned in compose.
4. Live proof (required):
   - `GET /health` → 200, `GET /ready` → 200
   - `POST /v1/recommend` with a REAL session from the dataset → 200,
     `model_version=ranker-retailrocket-v1`, items from real inventory
   - event → processor → re-rank loop demonstrated via API + session store
5. Record: model version, holdout metrics, image digest, sample request/response.

## 5. Acceptance Criteria

```
AC — production deploy
  ✓ Given RetailRocket events.csv on disk, When training runs, Then MLflow run + artifact dir exist with metrics
  ✓ Given holdout split, When evaluated, Then ranker NDCG@10 > popularity NDCG@10 (same split)
  ✓ Given triprank-api:prod image, When started, Then /ready 200 with real model loaded (no fallback version)
  ✓ Given live stack, When POST /v1/recommend with real session, Then 200 + real item ids + model_version=ranker-retailrocket-v1
  ✓ Given full pytest, When run, Then 40+ passed, ruff clean (no regressions)
```

## 6. Rollback

- Model: previous `artifacts/` dir + image tag retained; re-point and restart api.
- Stack: `docker compose down && docker compose up -d` on last-known-good.
- Data: `data/raw/` is source of truth; re-run training after adapter fix.

## 7. Out of Scope (this addendum)

Trivago download (needs creds), OTTO training, V4, cloud deploy, real A/B.
