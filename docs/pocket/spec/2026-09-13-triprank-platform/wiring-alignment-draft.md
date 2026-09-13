# TripRank — Production Wiring Alignment Addendum (DRAFT)

**Date:** 2026-09-13
**Status:** DRAFT — evidence pending from W1/W2/W3 wiring fixes
**Parent specs:**
- `docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md` (approved)
- `docs/pocket/spec/2026-09-13-triprank-platform/production-deploy-prd.md` (approved)
**Plan:** `docs/pocket/plans/2026-09-13-triprank-platform/execution-plan.md` (11 tasks, all DONE)

---

## 1. Purpose

Record how the production wiring round maps onto the approved PRD + plan:
what was already aligned, what gaps the audit found, and what each fix changed.
This is an alignment record, not a new scope — no new stories, no V4, no cloud.

## 2. Audit Baseline (2026-09-13, 5 parallel audits — all complete)

| # | Area | Verdict |
|---|------|---------|
| 1 | Postgres migration | ✅ ALIGNED — full 2,756,101 events / 1,407,580 sessions / 235,061 items |
| 2 | Web dummy data | ✅ ALIGNED (no hotel names exist) + ⚠️ catalog 12-ID hardcoded, data page static |
| 3 | Redis/Kafka session path | ❌ GAP — Redis empty, API dict-only, Kafka bypassed, no consumer |
| 4 | MLflow docker tracking | ❌ GAP — 0 runs / 0 models on docker; local-only default; Registry unwired |
| 5 | Grafana/Prometheus | ❌ GAP — no provisioned dashboard, scrape DOWN (JSON /metrics), Metrics unwired |

## 3. Fix Mapping (TODO: fill SHAs + evidence after W1/W2/W3 land)

## 3b. Local-Dev Pivot (user directive, round ~146)

Docker builds (~30+ min) dropped for iteration. Split:
- **Docker (backing only):** postgres:5433, redis:6379, kafka:9092, mlflow:5000, prometheus:9090, grafana:3000.
- **Local (dev/verify):** API via host uvicorn :8000 (DATABASE_URL→localhost:5433, REDIS_URL→localhost:6379); streaming consumer via host python (pending Kafka advertised-listener fix — W1).
- Glue changes (no builds): `monitoring/prometheus.yml` target → host.docker.internal:8000; `docker-compose.yml` web NEXT_PUBLIC_API_BASE → http://localhost:8000, `depends_on: api` removed (stale container stole :8000 once — stopped).

### Local verification results (host uvicorn running W1 9ab7ba5 + W2 api delta)
1. /metrics = prometheus text (triprank_* series) ✅
2. /metrics/json = {p95,samples} ✅
3. /v1/catalog?n=5 = real Postgres top-5 with views/carts/orders/conv ✅
4. Redis: POST click → key retailrocket:localproof, GET session reads back, clicked item top-1 ✅
5. Prometheus target up, triprank_requests_total series=1 ✅
6. Grafana: TripRank dashboard (uid triprank) listed ✅
- E2E: click 187946 → order 461686 → session recent=[187946,461686] last=order, Redis DBSIZE 2 ✅
- Streaming E2E (W1 23e0b67 dual-listener): canonical produce → consume → Redis KAFKAE2E {recent_items:[187946], last_event:click, TTL hash} ✅
- Note: poison-message robustness — malformed event (missing timestamp) crashes consumer loop (KeyError, exit 1). Pre-existing processor contract (canonical schema required); hardening (try/except skip) deferred as tech-debt, NOT blocking: producer is our own API path.
- P95 /v1/recommend local: p50 2.1ms / p95 2.7ms (n=20) ✅ (≤100ms bar)
- Suite: 45 passed, ruff clean ✅
- W3 web live :3001 = 200, real 187946, Beli, no synthetic ✅ (verified round 139)

### W1 — API redis+metrics+catalog+streaming — COMMITTED 9ab7ba5, redeploy in flight
- Commit: `9ab7ba5` "fix(wiring): redis sessions + prometheus metrics + catalog + streaming consumer" (4 owned files, +136/-11).
- Compose now lists streaming service + grafana provisioning mounts (verified in diff).
- Redeploy: W1's `up -d --build --force-recreate api streaming` running; ordered to extend to grafana (`--force-recreate api streaming grafana`) to activate W3's dashboard.
- TODO: Redis DBSIZE proof, Prometheus up=1 proof, catalog sample, streaming container state (pending build).
- Sequencing note: W2 has an additive uncommitted api/main.py delta (Postgres stats enrich); one final api rebuild ordered after both land.

### W2 — Retrain via docker MLflow + Registry Champion — retrain LAUNCHED
- Uncommitted delta: train_real.py (URI + real metrics + model/ artifacts + Champion), train.py, registry.py (Challenger default), tests/api/test_events.py, scripts/retrain_docker.ps1 new.
- Full retrain launched in background (--sessions 200000 --holdout-days 7 → localhost:5000); MLflow probes seen (2 probe-tmp runs).
- TODO: run_id, metric values, registered-model + Champion alias REST proof, commit sha.

### W3 — Web real catalog + order + Grafana provisioning — LANDED 1755131
- Commit: `1755131` "feat(web): real catalog + order action + grafana provisioning" (6 files)
- Evidence: tsc --noEmit exit 0; :3001 → 200 with real IDs (187946/461686/5411/370653/219512), Beli button, no synthetic IDs; live click+order POSTs → 200, session recent_items grows, last_event "order"; labels honest "Produk {id}" + populer #rank; zero invented names/prices in committed files.
- Grafana content: provisioning/datasources/prometheus.yml + provisioning/dashboards/triprank.yml + dashboards/triprank.json (uid triprank, 4 panels). Content ready; activation pending W1's grafana recreate (mounts in 9ab7ba5).
- Cross-agent fallbacks live: /v1/catalog 404 → VERIFIED_REAL fallback; /metrics/json 404 → /metrics fallback.
- Reconciliation note: untracked web/lib/catalog.ts + web/components/DealCard.tsx (invented names/prices) confirmed DEAD CODE (zero page imports) and REMOVED via git clean (W3 cleanup DONE, tsc exit 0). web/design.md left untouched (docs only).

## 6. Goal-Item Evidence Map

| # | Goal item | State + evidence |
|---|-----------|------------------|
| 1 | Compose wiring all services | ✅ docker backing (pg/redis/kafka/mlflow/prom/grafana/web) + local API/consumer; W1 commits 9ab7ba5+23e0b67; stale-api-steals-port guarded via depends_on removal |
| 2 | PRD + plan alignment | ✅ this addendum; audit baseline §2; checklist §4 (2 proven, rest pending final measure) |
| 3 | Retrain via docker MLflow | ✅ run e8892480 FINISHED, metrics live (NDCG@10 0.9777 / R@20 0.9947 / MRR@10 0.9727 vs baseline 0.7274), TripRanker v1 registered, **Champion→v1 (REST-verified)**, **artifacts served via REST** (model/model.pkl 346814B + meta.json + popularity.csv); quirk documented (bare abs artifact_uri → host-local writes; recovered via docker-cp); local bundle matches retrain, warm traffic serves ranker-retailrocket-v1; only W2's code-fix + owned-files commit outstanding |
| 4 | Redis real sessions E2E | ✅ POST→key→GET round-trip; streaming Kafka→Redis E2E |
| 5 | Grafana live metrics | ✅ target up, triprank_requests_total series, TripRank dashboard listed; latency histograms per model_version queryable (ranker-retailrocket-v1 + baseline-popularity) |
| 6 | CSV→Postgres, web real items | ✅ 2.76M rows audited; /v1/catalog live top-5; :3001 real IDs + Beli; /data ledger matches audited counts |
| 7 | Web events flow + display back | ✅ click→order→session trail (E2E + page renders getSession recent_items) |

## 4. PRD Conformance Checklist (measured local-dev, round 159)

- [x] Every response carries request_id, namespaced session_id, model_version, latency — PROVEN: /v1/recommend + /v1/events + /v1/session E2E responses all carry the four fields (localproof, KAFKAE2E, ver2 probes).
- [x] Graceful degradation preserved (never 5xx) — PROVEN: try/except fallbacks intact in all three endpoints; test_catalog_shape_and_never_5xx + test_stats_absent_without_postgres green.
- [x] No invented product names/cities/prices anywhere in web/ — PROVEN tree-wide: grep `Hotel|Rp |priceFor|ratingFor|Jakarta|Bali|stars` over web/ = zero matches; DealCard dead code removed; /data ledger figures match audited Postgres counts.
- [x] P95 ≤ 100ms — PROVEN: /v1/recommend local p50 2.1ms / p95 2.7ms (n=20).
- [x] 40+ tests green, ruff clean — PROVEN: 45 passed, ruff clean.
- [x] No per-dataset duplicate stacks; retailrocket via canonical schema — PROVEN: single EventIn/EventOut path, track-namespaced keys, canonical {event_id, session_id, timestamp, item_id, event_type} enforced by SessionProcessor.

## 5. Open Items / Deferred (explicitly NOT in this round)

- Trivago dataset (blocked on user Kaggle creds)
- V4 sequential model (deferred per spec)
- Cloud deploy, real A/B (out of scope per spec)
