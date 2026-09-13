# TripRank — Real-Time Session Recommendation & MLOps Platform (Full Spec)

**Date:** 2026-09-13
**Status:** approved
**Author:** brainstorm session
**Spec path:** docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md

---

## Summary

TripRank is a production-style session-based hotel recommendation platform with a complete MLOps lifecycle. Dual dataset adapters (Trivago Track A primary, OTTO Track B scalability benchmark) normalize to a canonical event schema feeding a shared feature → candidate → LightGBM ranking pipeline, served behind a versioned FastAPI with real Kafka + Redis real-time session state, MLflow native tracking/Registry with gated Champion–Challenger promotion, step-gated canary + auto-rollback, and drift-triggered retraining with Prometheus/Grafana observability.

---

## Context

### Current State

Greenfield workspace — `D:\programming\big-data\triple-recommendation-mlops` is empty. No manifests, code, tests, ADRs, or CONTEXT.md. Phase 1 scan found nothing to reuse; all conventions are greenfield choices made in this spec.

### Problem / Motivation

Travel recommendation must react to fast-changing in-session intent (search → click → filter → click), while ML production needs reproducible training, versioned deployment, safe rollout, and degradation detection. TripRank solves both: real-time session understanding plus a full experiment → validation → registry → canary → monitoring → retraining loop, positioned for a tiket.com MLE internship story.

### Related Areas

- `src/data/` ingestion, validation, preprocessing (adapters + canonical schema)
- `src/features/` session feature pipeline
- `src/models/` V1 baseline, V2/V3 LightGBM ranker, V4 reserved session-model interface, inference
- `src/training/`, `src/evaluation/`, `src/streaming/` (producer/consumer/processor), `src/monitoring/` (drift/metrics)
- `api/` FastAPI (`/v1/recommend`, `/health`, `/ready`), `docker/`, `monitoring/` (prometheus/grafana), `.github/workflows/`, `docs/`, `tests/`, `notebooks/`

---

## Scope

### In-Scope

- Trivago + OTTO dataset adapters → canonical event schema → shared pipeline (both tracks working in MVP)
- Session feature pipeline, candidate retrieval (≤500, item-similarity + popularity), V1 baselines, V2/V3 LightGBM ranker
- V4 SASRec/GRU4Rec deferred with reserved session-model interface (no training/serving in this cycle)
- MLflow experiment tracking + native Model Registry (stages + Champion/Challenger aliases), automated quality gates
- FastAPI `POST /v1/recommend`, `GET /health`, `GET /ready`, Docker + docker-compose (FastAPI, MLflow, real Kafka, Redis, Prometheus, Grafana)
- Real Kafka → session processor → Redis real-time state; graceful degradation on failures
- Step-gated canary 95/5→75/25→50/50→0/100 + auto-rollback; drift detection (PSI bands) + retrain triggers; CI/CD; docs + portfolio UI pages

### Out-of-Scope

- Real payment/booking/accounts/inventory — simulated production via public datasets; reason: portfolio, no real commerce
- Production millions-user scale / load proof — simulated ≥99% availability targets; reason: local compose, not cloud spend
- Personalized pricing — reason: separate problem, excluded from ranking MVP
- LLM travel agent — reason: out of recommender/MLOps story
- Real customer A/B testing — canary simulation only; reason: no live traffic
- V4 sequential model training/serving — deferred, interface reserved; reason: ranker-first progression tells a better portfolio story

---

## Architecture Constraints

- Layers this work may touch: ingestion/adapters, features, models/training/eval, MLflow/registry, FastAPI serving, streaming (Kafka/processor/Redis), monitoring/drift, CI/CD, docs/dashboards
- Layers this work must NOT touch: none pre-existing (greenfield); must NOT create per-dataset duplicate stacks (`trivago_model.py` / `otto_api.py` anti-pattern) — all downstream of canonical schema stays dataset-agnostic
- Patterns that must be followed: adapter → canonical schema → shared pipeline; modular monolith + streaming sidecar; graceful degradation (never 5xx to user on model failure); every response/log carries request_id, session_id (namespaced), model_version, latency
- Architecture validation result: PASS (see Phase 6 checklist in session; all boxes checked)

---

## Dependencies

### Existing (to leverage)

None — greenfield, no manifest found. pocket-planning Phase 0 will establish: python, fastapi, uvicorn, lightgbm, scikit-learn, pandas, mlflow, kafka-python/confluent-kafka, redis, prometheus-client, pytest, ruff.

### New (proposed)

- `lightgbm` — required MVP ranker (Q4 locked); alternatives rejected: xgboost (viable but second; stretch comparison only), hand-rolled ranker (rejected: commodity LTR, no justification)
- `mlflow` — tracking + native Registry; alternatives rejected: custom registry DB (rejected Q9: unnecessary service surface for portfolio)
- Real Kafka + Redis via compose (Q7 locked); test substitutes (redpanda/fakeredis/testcontainers) are test-only, not prod replacements
- `prometheus-client` + Grafana — metrics/dashboards (commodity observability, not hand-rolled)

*(No hand-rolled crypto/auth/parsing/retry/date-time/validation/caching — all commodity needs use established libs.)*

---

## Stories + Scenarios

Canonical event schema (locked): `{event_id, session_id, timestamp, item_id, event_type, context{city, device, filters}}` where `context.*` are OPTIONAL (H1: nulls valid, downstream null-safe). Session keys namespaced `trivago:<id>` / `otto:<id>`; API accepts optional `track` default `trivago` (H2). Timestamps are UTC epoch seconds; late arrival ≤7 days else quarantine (H13). Session TTL 30 min sliding; expired/missing → cold-start path (H6). Ordering: timestamp authority (stale `ts < stored last_ts` ignored), per-session-key serialization, atomic Redis writes (H3/H4/H5). P95 = API-edge server time over trailing 1000 requests (H8). Offline metrics averaged over 3 fixed seeds; gate ties PASS on strict ≥ (H11). Canary steps need 500-request windows (5xx ≤1% + P95 ≤100ms); rollback on 5xx >2% OR P95 >200ms over trailing 500 (H9/H10). MLflow/registry outage → queue locally + BLOCK promotion (H12). Retrain triggers debounced 24h per trigger type (H14).

### Story 1: Ranked recommendation

> As an End User, I want hotel recommendations based on my current session, so that I discover relevant stays faster.

**Rule 1: Top-K ranked response with version traceability**

- Example A: S123 (Bali + clicks H10,H21) → ordered ≤20, `model_version=ranker-vX`, latency counts to P95
- Example B: unknown S999 → 200 popularity list, `model_version=baseline-popularity`
- Example C: corrupt artifact → 200 fallback, `model_version=fallback`, error log with request_id + expected version
- Example D: `{}` body → 422; 0 candidates everywhere → 200 empty list with `reason=no_candidates` (H7)

```gherkin
Scenario: Happy-path ranking
  Given session trivago:S123 with city=Bali and recent_items=[H10,H21]
  When POST /v1/recommend {"session_id": "S123", "track": "trivago"}
  Then 200 with ≤20 items ordered by score desc, body carries model_version + request_id, server-time latency counted toward trailing-1000 P95 ≤100ms

Scenario: Cold-start fallback
  Given session trivago:S999 with no stored state (missing or TTL-expired >30min sliding)
  When POST /v1/recommend {"session_id": "S999"}
  Then 200 popularity list with model_version=baseline-popularity

Scenario: Corrupt artifact degrades gracefully
  Given champion artifact fails to load at request time
  When POST /v1/recommend {"session_id": "S123"}
  Then 200 fallback list with model_version=fallback and an ERROR log carrying request_id + expected version

Scenario: Missing session_id rejected
  Given request body {}
  When POST /v1/recommend
  Then 422 with validation error (no session_id to echo; logging uses request_id + model_version=none)

Scenario: Short candidate list returned as-is
  Given retrieval yields 0<n<K candidates
  When POST /v1/recommend
  Then 200 with exactly n items, no padding

Scenario: Total-empty inventory response
  Given retrieval + popularity fallback both yield 0 items
  When POST /v1/recommend
  Then 200 empty list with reason=no_candidates (never 404, never infinite fallback loop)
```

### Story 2: Real-time session state

> As an ML Engineer, I want user events captured and session state available at low latency, so that ranking reacts to changing intent.

**Rule 1: Idempotent, ordered, atomic state updates**

- Example A: click H33 on [H10,H21] → appends H33, `last_event=click`, `last_ts` advances
- Example B: duplicate evt_123 redelivery → single application
- Example C: stale event (ts < last_ts) → ignored
- Example D: OTTO order without city → canonical `context.city=null`, pipeline still scores

```gherkin
Scenario: Click updates session state
  Given Redis trivago:S123 recent_items=[H10,H21] last_ts=T
  When event evt_999 {session S123, click H33, ts=T+1} flows Kafka→processor→Redis
  Then atomic write sets recent_items includes H33, last_event=click, last_ts=T+1, visible to next recommend

Scenario: Duplicate event is idempotent
  Given evt_123 already applied to trivago:S123
  When evt_123 is redelivered (same payload)
  Then state unchanged; no double-apply

Scenario: Stale event ignored
  Given trivago:S123 last_ts=T+5
  When event with ts=T+2 arrives
  Then event ignored; state keeps last_ts=T+5

Scenario: OTTO null-context mapping
  Given OTTO {session s9, order a42, no city/device/filters}
  When adapter normalizes to canonical under key otto:s9
  Then context.city=null, context.device=null, context.filters=null; downstream scores without rejection

Scenario: Namespace isolation
  Given trivago:S1 and otto:S1 both exist as raw ids
  When events arrive for each
  Then Redis keys trivago:S1 and otto:S1 hold independent states
```

### Story 3: Candidate generation

> As a Recommendation Engine, I want a relevant ≤500 candidate set, so that the ranker never scores full inventory.

**Rule 1: Narrow then fallback**

- Example A: 100k inventory → ≤500 to ranker
- Example B: segment matches ∅ → global popularity instead of empty

```gherkin
Scenario: Retrieval narrows inventory
  Given inventory >100k items and session S123
  When candidate generation runs
  Then ≤500 candidates pass to the ranker

Scenario: Empty segment falls back
  Given segment filter matches zero items
  When candidate generation runs
  Then global popularity list is returned instead of an empty set
```

### Story 4: Ranking + offline evaluation

> As an ML Engineer, I want LightGBM-ranked candidates with standardized offline metrics, so that models compare objectively.

**Rule 1: LightGBM MVP ranker; baseline-first; 3-seed averages**

- Example A: 500 candidates → ordered Top-K, deterministic tie-break
- Example B: no baseline for track → challenger comparison BLOCKED

```gherkin
Scenario: Ranker orders candidates
  Given 500 candidates + session features for S123
  When LightGBM ranker scores
  Then Top-K ordered by score desc with deterministic tie-break

Scenario: Baseline precedes challenger comparison
  Given no popularity/item-sim baseline NDCG@10 + Recall@20 for the track
  When a LightGBM run claims improvement
  Then comparison BLOCKED until baselines exist for that track

Scenario: Offline metrics are seeded averages
  Given a finished evaluation
  When metrics inspected
  Then NDCG@10/Recall@20/MRR@10 are means over 3 fixed seeds with seed values recorded
```

### Story 5: Experiment tracking + registry

> As a Data Scientist, I want every run reproducible and validated models registered, so that only traceable versions deploy.

**Rule 1: Full provenance; outage queues + blocks**

```gherkin
Scenario: Run is reproducible
  Given a finished training run
  When inspected in MLflow
  Then params, NDCG@10, Recall@20, artifacts, dataset_version, and git_commit are all present (dirty git flagged, not silently logged)

Scenario: Validated model registered
  Given a run passing the quality gate
  When registered as HotelRanker candidate
  Then version + stage + training-run linkage exist before any traffic

Scenario: Tracking outage queues and blocks
  Given MLflow/Registry unreachable during training
  When run finishes
  Then run payload queued locally with retry; promotion BLOCKED until logging succeeds
```

### Story 6: Automated quality gate

> As an ML Engineer, I want poor models blocked automatically, so that only validated challengers reach canary.

**Rule 1: PASS iff NDCG@10 ≥ champion AND Recall@20 ≥ champion AND P95 ≤ 100ms AND error ≤ 1% (strict ≥, ties PASS)**

```gherkin
Scenario: Challenger passes
  Given champion NDCG@10=0.82, challenger 0.85, P95=72ms edge-measured, err=0.4%
  When gate evaluates
  Then PASS; challenger becomes canary-eligible

Scenario: Latency fails a better model
  Given challenger NDCG@10=0.86 but P95=140ms
  When gate evaluates
  Then FAIL; no registry stage change

Scenario: Exact tie passes
  Given challenger NDCG@10 equals champion to all reported precision
  When gate evaluates
  Then PASS on the metric leg (strict ≥ semantics)
```

### Story 7: Canary + rollback

> As an ML Engineer, I want challengers exposed gradually with auto-rollback, so that production behavior is validated before full rollout.

**Rule 1: Gated ladder; 5xx/timeout rollback**

```gherkin
Scenario: Canary advances on green health
  Given 95/5 split with challenger 5xx ≤1% and P95 ≤100ms over a 500-request window
  When step gate evaluates
  Then traffic advances to 75/25

Scenario: Error breach rolls back
  Given canary at 75/25 with challenger 5xx 2.6% over trailing 500 requests
  When health evaluated
  Then traffic returns to 100% champion; challenger marked unhealthy

Scenario: Latency breach rolls back
  Given challenger P95 >200ms over trailing 500 requests at any canary step
  When health evaluated
  Then traffic returns to 100% champion
```

### Story 8: Monitoring + drift + retraining

> As an SRE/DS, I want system + ML + business-proxy visibility with debounced retrain triggers, so that degradation is caught without trigger storms.

**Rule 1: PSI bands + NDCG-drop trigger, 24h debounce per trigger type**

```gherkin
Scenario: Significant drift triggers retrain signal
  Given hotel_price PSI=0.31 over the evaluation window
  When drift job runs
  Then status=RETRAIN RECOMMENDED naming feature + PSI; retraining triggerable (suppressed if same trigger fired <24h ago)

Scenario: Model degradation triggers retrain signal
  Given training NDCG=0.82 and production NDCG=0.74 (>5% drop)
  When performance evaluated
  Then retraining trigger fires with both values recorded (same 24h debounce)
```

### Story 9: Data validation

> As a Data Engineer, I want incoming data validated, so that corrupt data never enters the pipeline.

**Rule 1: Quarantine on failure; UTC epoch + 7-day lateness bound**

```gherkin
Scenario: Corrupt batch quarantined
  Given a batch with invalid timestamps + duplicate event_ids
  When validation runs
  Then batch quarantined with per-check failure counts; nothing enters features

Scenario: Late arrival quarantined
  Given an event with timestamp older than 7 days
  When validation runs
  Then event quarantined as late-arrival; adapter accepts only UTC epoch seconds otherwise
```

### Story 10: Reliability + traceability

> As a Platform Engineer / Lead, I want health/readiness separation and per-request traceability, so that incidents are investigable.

**Rule 1: /health liveness vs /ready readiness; trace fields on responses + logs**

```gherkin
Scenario: Health vs readiness
  Given API with model loaded but Redis unreachable
  When GET /health and GET /ready
  Then /health 200 (process alive); /ready 503 until Redis recovers

Scenario: Request traceability
  Given any /v1/recommend call
  When response + logs inspected
  Then request_id, namespaced session_id (when supplied), model_version, latency all present (422 path uses request_id + model_version=none)
```

---

## Acceptance Criteria

```
ACCEPTANCE CRITERIA — TripRank full platform
Date: 2026-09-13 | Scope confirmed: yes (full platform, dual-track)

Rule: Ranked response
  ✓ Given session with state, When POST /v1/recommend, Then ≤20 score-ordered items + model_version + request_id, P95 (edge, trailing 1000) ≤100ms
  ✓ Given unknown/expired session, When POST /v1/recommend, Then 200 popularity list model_version=baseline-popularity
  ✓ Given corrupt artifact, When POST /v1/recommend, Then 200 fallback model_version=fallback + ERROR log (request_id + expected version)
  ✓ Given 0<n<K candidates, When POST /v1/recommend, Then 200 with exactly n items
  ✓ Given 0 candidates everywhere, When POST /v1/recommend, Then 200 empty + reason=no_candidates
  ✗ Given body without session_id, When POST /v1/recommend, Then 422

Rule: Session state
  ✓ Given click event, When Kafka→processor→Redis, Then atomic state update visible to next recommend
  ✓ Given duplicate event_id, When redelivered, Then single application
  ✓ Given stale ts < last_ts, When event arrives, Then ignored
  ✓ Given OTTO context-less event, When normalized, Then nulls valid under otto: namespace, pipeline scores

Rule: Candidates + ranking
  ✓ Given large inventory, When retrieval runs, Then ≤500 candidates
  ✓ Given LightGBM run, When evaluated, Then seeded-mean NDCG@10/Recall@20/MRR@10 + baseline-first enforced

Rule: Tracking/registry/gate
  ✓ Given finished run, When inspected, Then params/metrics/artifacts/dataset_version/git_commit present
  ✓ Given tracking outage, When run finishes, Then queued + promotion BLOCKED
  ✓ Given challenger ≥ champion (both metrics) + P95≤100ms + err≤1%, When gate runs, Then PASS (ties PASS)
  ✗ Given any leg failing, When gate runs, Then FAIL with no stage change

Rule: Canary/rollback
  ✓ Given 500-req window green (5xx≤1%, P95≤100ms), When step gate runs, Then advance ladder
  ✓ Given 5xx>2% or P95>200ms over trailing 500, When evaluated, Then 100% champion rollback

Rule: Drift/retrain
  ✓ Given PSI>0.25 or NDCG drop>5%, When evaluated, Then RETRAIN RECOMMENDED + trigger (24h debounce per type)

Rule: Validation
  ✓ Given corrupt batch, When validation runs, Then quarantined with counts, pipeline untouched
  ✓ Given event older than 7 days / non-epoch timestamp, When validated, Then quarantined

Rule: Reliability
  ✓ Given Redis down, When probed, Then /health 200 + /ready 503
  ✓ Given any recommend call, When response/logs inspected, Then request_id + session/model_version + latency present

OPEN QUESTIONS (risks if unresolved):
  - Q1 success-layer got no selection → assumed: ML gates rule, system/business observe-only in MVP → risk: approver expected SLA/business promotion blocks
  - V4 reserved interface shape → assumed: design-time detail for planning → risk: minor rework if SASRec needs richer session encoding
  - Exact Grafana panel set → assumed: system + ML + business-proxy per brief §12 → risk: scope creep in dashboard phase

OUT-OF-SCOPE (remind pocket-planning):
  - Real payment/booking/accounts, production scale proof, personalized pricing, LLM agent, live A/B, V4 training/serving
```

---

## Design Decision

**Chosen option:** Option A — Modular monolith + streaming sidecar (recommended)

**Summary:** Single Python repo with `api/`, `src/{data,features,models,training,evaluation,streaming,monitoring}` modules plus Kafka→processor→Redis sidecar in compose; shared pipeline strictly downstream of the canonical schema. Satisfies all 10 story groups with the least operational surface for a portfolio while keeping the GCP path (Pub/Sub, Memorystore, Cloud Run/GKE) intact.

**Rejected options:**

- Option B (microservices per concern: separate candidate/ranker/session/registry services): rejected because zero traffic justifies no service-split complexity; violates greenfield simplicity and slows MVP without satisfying any scenario better.
- Option C (notebook-first + thin serving, simulated stream): rejected because it fails S2 real-time atomicity scenarios, S7 canary rollback realism, and the "real Kafka+Redis" locked answer (Q7); acceptable only as a Phase-1 stepping stone, not the spec target.

**Key tradeoffs accepted:**

- Real Kafka in compose (heavier local env) over simulated bus — accepted for interview-grade streaming credibility.
- Strict ≥ gate (ties PASS) over margin-based promotion — accepted simpler rule; noise handled by 3-seed averages rather than epsilon bands.
- 30-min sliding TTL + short-list passthrough over padding/TTL-long sessions — accepted simpler, more honest relevance behavior.

---

## Open Questions / Assumptions

| Question | Resolution | Risk if Wrong |
|----------|------------|---------------|
| Q1 success-layer (no selection) | assumed: ML gates rule; system/business observe-only | Approver may demand SLA/business promotion blocks — gate rework |
| Canary N-window / rollback scope (H9/H10) | resolved: 500-req windows; 5xx+timeout; P95>200ms rollback | Low — locked by explicit answers |
| P95 point / tie handling (H8/H11) | resolved: API-edge trailing-1000; strict ≥ ties PASS; 3-seed means | Low — locked by explicit answers |
| TTL + short-list + empty behavior (H6/H7) | resolved: 30-min sliding; short passthrough; empty 200 + reason | Low — locked by explicit answers |
| V4 interface shape | assumed: design-time detail | Minor rework if sequential model needs richer encoding |
| Grafana panel set | assumed: brief §12 (system + ML + business) | Dashboard scope creep |

---

## Implementation Notes

- Enforce `track` namespacing (`trivago:`/`otto:`) at adapter + Redis + API layers from day one — retrofitting risks state corruption.
- Redis session writes must be atomic (single LUA script/transaction writing recent_items + city + filters + last_ts together).
- P95 measured at API edge (server time) over trailing 1000 `/v1/recommend` requests; expose `model_version` label for per-version latency split.
- Quality gate consumes edge P95 + canary 5xx rates — keep metric definitions identical between gate and canary to avoid the §20 threshold-mismatch concern (gate err≤1% over eval window vs canary rollback >2% over trailing 500 are intentionally different stages; document both).
- Retrain triggers debounced 24h per trigger type (drift vs performance) with last-fire timestamps persisted.

---

## Rollback Plan

- Model: canary auto-rollback to 100% champion on 5xx>2% or P95>200ms (trailing 500); manual `alias Champion → previous version` if automation itself fails.
- Release: `docker compose` pinned images; `docker compose down && docker compose up <prev>` restores last-known-good serving stack.
- Data: quarantined batches never enter features; re-ingest from `data/raw` after adapter fix; registry stage demotion is a metadata-only revert.
