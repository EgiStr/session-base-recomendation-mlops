# EXECUTION PLAN — TripRank Real-Time Session Recommendation & MLOps Platform

**Date:** 2026-09-13
**Spec:** docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
**Status:** approved
**Total tasks:** 11
**Approval:** user GO (goal round) — full chain to running app authorized; dry-run parses (split, 3 phases)

---

## Execution Overview

### Recommended Order
```
T1 → T2 → T3, T7 (parallel) → T4 → T5, T6 (parallel) → T8 → T9 → T10 → T11
```

> Dependency order above is **recommended** — pocket skill enforces actual
> parallelism and sequencing based on its routing logic.

### Parallelizable Groups
| Group | Tasks | Unblocked After |
|-------|-------|-----------------|
| Group A | T3, T7 | T2 completes |
| Group B | T5, T6 | T4 completes |

### Constraints Reminder
**Architecture:** Modular monolith + streaming sidecar. Adapter → canonical schema → shared dataset-agnostic pipeline. No per-dataset duplicate stacks. Graceful degradation (never 5xx on model failure). Every response/log: request_id, namespaced session_id, model_version, latency. Track namespaces `trivago:`/`otto:` from day one. Atomic Redis writes. P95 = API-edge server time trailing-1000.
**Out-of-scope:** Real payment/booking/accounts, production scale proof, personalized pricing, LLM agent, live A/B, V4 training/serving.
**Assumptions at risk:** ML-gates-rule success layer (Q1 no selection); V4 interface shape design-time; Grafana panel set per brief §12.
**Sequencing:** Dependency order shown is recommended only — pocket enforces actual blocking rules.

### File Structure Map
```
Rule: Scaffold
  Create: pyproject.toml (created by: T1)
  Create: requirements.txt (created by: T1)
  Create: docker-compose.yml (created by: T1)
  Create: docker/Dockerfile.api (created by: T1)
  Create: .github/workflows/ci.yml (created by: T1)
  Create: README.md (created by: T1)
  Create: src/__init__.py (created by: T1)
  Create: api/__init__.py (created by: T1)
  Create: tests/__init__.py (created by: T1)

Rule: Session state + Validation (adapters, schema, validation)
  Create: src/data/schemas.py (created by: T2)
  Create: src/data/adapters/trivago.py (created by: T2)
  Create: src/data/adapters/otto.py (created by: T2)
  Create: src/data/validation.py (created by: T2)
  Create: src/data/ingestion.py (created by: T2)
  Test: tests/data/test_adapters.py
  Test: tests/data/test_validation.py

Rule: Candidates + features + baselines
  Create: src/features/feature_engineering.py (created by: T3)
  Create: src/models/candidates.py (created by: T3)
  Create: src/models/baseline.py (created by: T3)
  Test: tests/models/test_candidates.py
  Test: tests/features/test_features.py

Rule: Ranking + offline eval
  Create: src/models/ranker.py (created by: T4)
  Create: src/models/session_model.py (created by: T4)
  Create: src/evaluation/evaluate.py (created by: T4)
  Test: tests/models/test_ranker.py
  Test: tests/evaluation/test_metrics.py

Rule: Tracking/registry/gate
  Create: src/training/train.py (created by: T5)
  Create: src/registry/registry.py (created by: T5)
  Create: src/evaluation/quality_gate.py (created by: T5)
  Test: tests/training/test_quality_gate.py
  Test: tests/registry/test_registry.py

Rule: Ranked response + Reliability (API)
  Create: api/main.py (created by: T6)
  Create: src/models/inference.py (created by: T6)
  Test: tests/api/test_recommend.py

Rule: Streaming session state
  Create: src/streaming/producer.py (created by: T7)
  Create: src/streaming/consumer.py (created by: T7)
  Create: src/streaming/session_processor.py (created by: T7)
  Test: tests/streaming/test_session_processor.py

Rule: Canary/rollback
  Create: src/deployment/canary.py (created by: T8)
  Test: tests/deployment/test_canary.py

Rule: Drift/retrain + monitoring
  Create: src/monitoring/drift.py (created by: T8)
  Create: src/monitoring/metrics.py (created by: T9)
  Create: monitoring/prometheus.yml (created by: T9)
  Create: monitoring/grafana/dashboard.json (created by: T9)
  Test: tests/monitoring/test_drift.py
  Test: tests/monitoring/test_metrics.py

Rule: Compose + docs/UI
  Modify: docker-compose.yml
  Create: docker/Dockerfile.training (created by: T10)
  Create: docker/Dockerfile.streaming (created by: T10)
  Create: .github/workflows/model-validation.yml (created by: T10)
  Create: docs/architecture.md (created by: T10)
  Create: docs/ml-pipeline.md (created by: T10)
  Create: docs/deployment.md (created by: T10)
  Create: docs/monitoring.md (created by: T10)
  Create: ui/app.py (created by: T10)

Rule: E2E integration
  Test: tests/integration/test_e2e.py
```

---

## Pocket Packets

---

### Task 1: Scaffold repo, manifests, compose, CI [prereq]

## OBJECTIVE
Create runnable repo skeleton: manifests, package layout, compose, Dockerfile.api, CI, README.

Files:
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `docker-compose.yml`
- Create: `docker/Dockerfile.api`
- Create: `.github/workflows/ci.yml`
- Create: `README.md`
- Create: `src/__init__.py`, `api/__init__.py`, `tests/__init__.py`

Steps:
1. Create the structure / files / config (non-testable scaffold).
2. Verify: `python -c "import sys; print(sys.version)"` + `docker compose config` (or `python -m pip check` if docker absent) + `pytest --collect-only -q`.
3. Commit: `git init` if needed; `git add -A`; `git commit -m "chore(scaffold): repo skeleton manifests compose ci"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rule: Architecture Constraints + Related Areas; preflight: greenfield, pytest+pytest-asyncio, no helpers.
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: lightweight
Justification: 7 files, no branching logic, pure structure every later task depends on.

## SANDWICH CONTEXT
[CRITICAL: Adapter → canonical schema → shared dataset-agnostic pipeline; never per-dataset duplicate stacks]
You are implementing repo scaffold for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: pyproject.toml, requirements.txt, docker-compose.yml, docker/Dockerfile.api, .github/workflows/ci.yml, README.md, package __init__ files.
Available after: none (prereq)
Architecture rule: modular monolith layout src/{data,features,models,training,evaluation,streaming,monitoring} + api/; no microservice split.
[RESTATE: Adapter → canonical schema → shared dataset-agnostic pipeline; never per-dataset duplicate stacks]

## DELIVERABLE
Verification — task is DONE when:
- Repo installs (`pip install -e .` or `pip install -r requirements.txt` succeeds)
- `pytest --collect-only -q` exits 0 (zero tests ok)
- `docker compose config` parses (or documented skip if docker absent)

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - Python manifests pin fastapi, uvicorn, lightgbm, scikit-learn, pandas, mlflow, redis, prometheus-client, pytest, pytest-asyncio, httpx
  - compose declares api, mlflow, kafka, redis, prometheus, grafana
  - CI runs ruff + pytest
  - [no-tdd — structural task]

Must-not-have:
  - Real payment/booking/accounts; V4 training; per-dataset duplicate stacks
  - Modifications to files outside the listed scope

Open question risks: none (structural)

Rollback note:
  - Delete created files / `git reset --hard HEAD` pre-commit.

## STOP CONDITIONS
Done when: install + collect-only + compose config pass, commit created
Uncertain when: docker absent (document skip, still DONE_WITH_CONCERNS)
Escalate when: Prosper touches out-of-scope files

---

### Task 2: Canonical schema + Trivago/OTTO adapters + validation [depends: T1]

## OBJECTIVE
Implement canonical event schema, both adapters, validation with quarantine rules.

Files:
- Create: `src/data/schemas.py`
- Create: `src/data/adapters/trivago.py`
- Create: `src/data/adapters/otto.py`
- Create: `src/data/validation.py`
- Create: `src/data/ingestion.py`
- Test: `tests/data/test_adapters.py`
- Test: `tests/data/test_validation.py`

Steps:
1. Write failing test for: OTTO null-context mapping + namespace isolation + corrupt batch quarantine + late arrival quarantine.
   File: `tests/data/test_adapters.py` + `tests/data/test_validation.py`
   TDD first: tests below MUST fail on greenfield repo (ModuleNotFoundError) before any `src/data` code exists.
   ```python
   # tests/data/test_adapters.py
   # Given OTTO {session s9, order a42, no city/device/filters}
   # When adapter normalizes / Then context nulls valid under key otto:s9
   from src.data.adapters.otto import normalize_otto
   from src.data.adapters.trivago import normalize_trivago
   from src.data.schemas import namespaced_key

   def test_otto_null_context_mapping():
       # Given
       raw = {"session_id": "s9", "order_id": "a42", "item_id": "a42",
              "timestamp": 1757760000, "event_type": "order"}
       # When
       ev = normalize_otto(raw)
       # Then
       assert ev.session_id == "otto:s9"
       assert ev.context.city is None and ev.context.device is None
       assert ev.context.filters is None

   def test_namespace_isolation():
       # Given colliding raw ids / When namespaced / Then keys differ
       assert namespaced_key("trivago", "S1") != namespaced_key("otto", "S1")
       assert namespaced_key("trivago", "S1") == "trivago:S1"

   def test_trivago_adapter_happy_path():
       # Given trivago click / When normalized / Then canonical fields kept
       raw = {"session_id": "S1", "item_id": "H10", "timestamp": 1757760000,
              "event_type": "click", "city": "Bali", "device": "mobile"}
       ev = normalize_trivago(raw)
       assert ev.session_id == "trivago:S1"
       assert ev.context.city == "Bali"
   ```
   ```python
   # tests/data/test_validation.py
   # Given batch with invalid timestamps + duplicate event_ids
   # When validation runs / Then quarantined with per-check counts
   import time
   from src.data.schemas import CanonicalEvent, EventContext
   from src.data.validation import validate_batch

   def _ev(eid, ts):
       return CanonicalEvent(event_id=eid, session_id="trivago:S1",
           timestamp=ts, item_id="H1", event_type="click",
           context=EventContext())

   def test_corrupt_batch_quarantined_with_counts():
       # Given
       now = int(time.time())
       batch = [_ev("e1", now), _ev("e1", now), _ev("e2", "not-epoch")]
       # When
       report = validate_batch(batch)
       # Then
       assert report["quarantined"] == 2
       assert report["per_check"]["duplicate"] >= 1
       assert report["per_check"]["timestamp"] >= 1
       assert len(report["clean"]) == 1

   def test_late_arrival_quarantined():
       # Given event older than 7 days / When validated / Then late-arrival quarantine
       old = int(time.time()) - 8 * 86400
       report = validate_batch([_ev("e9", old)])
       # Then
       assert report["quarantined"] == 1
       assert report["per_check"]["late_arrival"] == 1
   ```
2. Run test — verify FAIL: `pytest tests/data -x -q`
   Expected failure: ModuleNotFoundError / assertion failures (modules do not exist yet).
3. Implement minimal code: CanonicalEvent dataclass (event_id, session_id, track, timestamp UTC epoch int, item_id, event_type, context{city?,device?,filters?} all Optional); `namespaced_key(track,id)`; trivago adapter → canonical; otto adapter → canonical with nulls; validation (schema/missing/dup/timestamp/ID/type + 7-day lateness bound) returning quarantine report with per-check counts.
4. Run test — verify PASS: `pytest tests/data -q`
5. Refactor while green (bounded); re-run `pytest tests/data -q` — must stay PASS.
6. Commit: `git add src/data tests/data`; `git commit -m "feat(data): canonical schema dual adapters validation"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rules: Session state (S2), Validation (S9); GWT: OTTO null-context, namespace isolation, corrupt quarantine, late arrival.
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: standard
Justification: 5 source files + 2 test files, cross-track namespacing judgment, edge-case heavy.

## SANDWICH CONTEXT
[CRITICAL: All downstream dataset-agnostic; context.* OPTIONAL nulls valid; keys track-namespaced from day one]
You are implementing canonical schema + adapters + validation for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: src/data/schemas.py, src/data/adapters/trivago.py, src/data/adapters/otto.py, src/data/validation.py, src/data/ingestion.py, tests/data/test_adapters.py, tests/data/test_validation.py.
Available after: T1
Architecture rule: downstream never branches on raw dataset shape; context null-safe; UTC epoch seconds only.
[RESTATE: All downstream dataset-agnostic; context.* OPTIONAL nulls valid; keys track-namespaced from day one]

## DELIVERABLE
Given OTTO {session s9, order a42, no city/device/filters}, When adapter normalizes, Then context.city=null, device=null, filters=null under key otto:s9; downstream scores without rejection.
Given trivago:S1 and otto:S1 raw ids, When events arrive, Then Redis keys hold independent states (unit: namespaced_key differs).
Given batch with invalid timestamps + duplicate event_ids, When validation runs, Then quarantined with per-check counts; nothing enters features.
Given event older than 7 days / non-epoch timestamp, When validated, Then quarantined as late-arrival.

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - Tests written BEFORE implementation (TDD)
  - Strict ≥ semantics not in this task; no gate logic here
  - Commit message follows conventional commits

Must-not-have:
  - Per-dataset downstream branches; rejecting null context; V4 training; real commerce fields

Open question risks: none resolved here (all H-blockers locked)

Rollback note:
  - `git revert` the feat commit; re-ingest from data/raw.

## STOP CONDITIONS
Done when: all DELIVERABLE scenarios pass, tests green, commit created
Uncertain when: dataset sample shape contradicts adapter assumptions → NEEDS_CONTEXT
Escalate when: touches files outside scope or creates duplicate per-dataset stacks

---

### Task 3: Features + candidate retrieval + V1 baselines [depends: T2]

## OBJECTIVE
Session features, ≤500 candidate retrieval (item-sim + popularity with global fallback), popularity/item-sim baselines.

Files:
- Create: `src/features/feature_engineering.py`
- Create: `src/models/candidates.py`
- Create: `src/models/baseline.py`
- Test: `tests/models/test_candidates.py`
- Test: `tests/features/test_features.py`

Steps:
1. Write failing test for: retrieval narrows + empty segment fallback + short-list passthrough.
   File: `tests/models/test_candidates.py`
   TDD first: tests MUST fail on greenfield repo (ModuleNotFoundError) before `src/features`/`src/models` code exists.
   ```python
   # tests/models/test_candidates.py
   # Given inventory >100k items (simulated with 1200) + session S123
   # When candidate generation runs / Then <=500 candidates pass to the ranker
   from src.models.baseline import item_similarity_rank, popularity_rank
   from src.models.candidates import generate_candidates

   def _inv(n, city="Bali"):
       return [{"item_id": f"H{i}", "city": city, "pop": n - i} for i in range(n)]

   def _sess(**kw):
       base = {"recent_items": ["H5"], "city": "Bali", "filters": None}
       base.update(kw)
       return base

   def test_retrieval_narrows_to_cap():
       # Given
       cands = generate_candidates(_sess(), _inv(1200))
       # Then
       assert len(cands) <= 500

   def test_empty_segment_falls_back_to_global():
       # Given segment filter matches zero items / When runs / Then global popularity
       cands = generate_candidates(_sess(city="Nowhere"), _inv(50))
       # Then
       assert cands == popularity_rank(_inv(50), k=500)
       assert len(cands) > 0

   def test_short_list_passthrough_no_padding():
       # Given retrieval yields 0<n<K / When consumed / Then exactly n items
       cands = generate_candidates(_sess(), _inv(3), k=20)
       # Then
       assert len(cands) == 3
   ```
   ```python
   # tests/features/test_features.py
   # Given null context / When features built / Then no raise, defaults present
   from src.features.feature_engineering import build_session_features

   def test_features_null_safe():
       # Given OTTO-style context-less session / When built / Then valid defaults
       feats = build_session_features({"recent_items": [], "city": None, "filters": None})
       # Then
       assert feats["recent_items"] == [] and feats["city"] is None

   def test_features_keep_recent_items():
       # Given session with clicks / When built / Then recent items preserved
       feats = build_session_features({"recent_items": ["H10", "H21"], "city": "Bali", "filters": None})
       # Then
       assert feats["recent_items"] == ["H10", "H21"] and feats["city"] == "Bali"
   ```
2. Run test — verify FAIL: `pytest tests/models/test_candidates.py tests/features -x -q`
3. Implement: session feature builder (recent_items, city, filters, recency, null-safe); candidate retrieval cap 500; popularity scorer; item-similarity scorer; global popularity fallback; short lists returned as-is (no padding).
4. Run test — verify PASS: `pytest tests/models/test_candidates.py tests/features -q`
5. Refactor while green; re-run — must stay PASS.
6. Commit: `git add src/features src/models/candidates.py src/models/baseline.py tests/models/test_candidates.py tests/features`; `git commit -m "feat(ranking): features candidates baselines"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rules: Candidates (S3), Ranking baseline-first (S4).
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: standard
Justification: 3 source files, retrieval + scoring judgment, null-safe features.

## SANDWICH CONTEXT
[CRITICAL: Retrieval output ≤500; empty segment → global popularity; short lists unpadded; downstream dataset-agnostic]
You are implementing features + candidates + baselines for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: src/features/feature_engineering.py, src/models/candidates.py, src/models/baseline.py, tests/models/test_candidates.py, tests/features/test_features.py.
Available after: T2
Architecture rule: features consume CanonicalEvent only; null context must not raise.
[RESTATE: Retrieval output ≤500; empty segment → global popularity; short lists unpadded; downstream dataset-agnostic]

## DELIVERABLE
Given inventory >100k items and session S123, When candidate generation runs, Then ≤500 candidates pass to the ranker.
Given segment filter matches zero items, When candidate generation runs, Then global popularity list returned instead of empty set.
Given retrieval yields 0<n<K, When recommend consumes, Then exactly n items (no padding) — enforced jointly with T6.

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - TDD order; deterministic popularity tie-break; null-safe features
  - No LightGBM here (T4); no API here (T6)

Must-not-have:
  - Padding short lists; per-dataset branches; V4 model code beyond interface stub (T4 owns stub)

Open question risks: none

Rollback note: `git revert` feat commit.

## STOP CONDITIONS
Done when: DELIVERABLE passes, tests green, commit created
Escalate when: touches out-of-scope files

---

### Task 4: LightGBM ranker + V4 interface stub + offline eval [depends: T3]

## OBJECTIVE
LGBMRanker training/inference with group handling, deterministic tie-break, seeded-mean offline metrics (NDCG@10/Recall@20/MRR@10 over 3 fixed seeds), V4 reserved session-model interface (stub only).

Files:
- Create: `src/models/ranker.py`
- Create: `src/models/session_model.py`
- Create: `src/evaluation/evaluate.py`
- Test: `tests/models/test_ranker.py`
- Test: `tests/evaluation/test_metrics.py`

Steps:
1. Write failing test for: ranker orders candidates + baseline-first block + seeded means recorded.
   File: `tests/models/test_ranker.py`, `tests/evaluation/test_metrics.py`
   TDD first: tests MUST fail on greenfield repo (ModuleNotFoundError) before `src/models/ranker.py` exists.
   ```python
   # tests/models/test_ranker.py
   # Given tiny synthetic group data (2 queries x 5 docs) so tests run <5s
   import numpy as np
   from src.models.ranker import LGBMRanker
   from src.models.session_model import SessionModelProtocol

   def _toy():
       rng = np.random.RandomState(0)
       X = rng.rand(10, 4)
       y = np.array([2, 1, 0, 0, 0, 1, 2, 0, 0, 0])
       return X, y, [5, 5]

   def test_ranker_orders_with_deterministic_tiebreak():
       # Given 10 docs in 2 groups / When scored / Then desc with item_id asc tie-break
       r = LGBMRanker().fit(*_toy())
       scores = r.predict(np.zeros((3, 4)))
       ranked = r.rank(["H3", "H1", "H2"], scores)
       # Then: order follows score desc; equal scores fall back to item_id asc
       assert ranked == sorted(ranked, key=lambda i: (-scores[["H3", "H1", "H2"].index(i)], i))

   def test_ranker_fit_is_fast_on_toy():
       # Given toy data / When fit / Then group math consistent (sum(group)=n)
       X, y, g = _toy()
       assert sum(g) == len(X)
       LGBMRanker().fit(X, y, g)  # must finish in well under 5s

   def test_v4_stub_raises_not_implemented():
       # Given V4 reserved interface / When fit called / Then NotImplementedError (stub only)
       import pytest
       with pytest.raises(NotImplementedError):
           SessionModelProtocol().fit(None, None)
   ```
   ```python
   # tests/evaluation/test_metrics.py
   # Given finished evaluation / When inspected / Then 3-seed means recorded
   from src.evaluation.evaluate import compare, evaluate

   def test_evaluate_records_seeded_means():
       # Given trivial ranked vs relevant / When evaluated / Then seeds [42,7,123] recorded
       res = evaluate({"q1": ["H1", "H2", "H3"]}, {"q1": {"H2"}}, k=10)
       # Then
       assert res["seeds"] == [42, 7, 123]
       assert {"ndcg@10", "recall@20", "mrr@10"} <= set(res)

   def test_compare_blocked_without_baseline():
       # Given no baseline metrics / When challenger claims improvement / Then BLOCKED
       out = compare({"ndcg@10": 0.9}, None)
       # Then
       assert out["status"] == "BLOCKED"
   ```
2. Run test — verify FAIL: `pytest tests/models/test_ranker.py tests/evaluation -x -q`
3. Implement: ranker train (lambdarank, group sizes, eval_at) + predict with deterministic tie-break (score desc, item_id asc); evaluate() computing Recall@K/NDCG@K/MRR@K means over seeds [42,7,123]; compare() BLOCKED without baseline metrics for track; SessionModelProtocol stub (fit/predict signatures raising NotImplementedError).
4. Run test — verify PASS: `pytest tests/models/test_ranker.py tests/evaluation -q`
5. Refactor while green; re-run — must stay PASS.
6. Commit: `git add src/models/ranker.py src/models/session_model.py src/evaluation/evaluate.py tests/models/test_ranker.py tests/evaluation`; `git commit -m "feat(ranking): lightgbm ranker seeded eval v4-stub"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rule: Ranking + offline eval (S4); LightGBM docs (LGBMRanker group required, lambdarank).
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: standard
Justification: 3 source files, LTR group semantics + metric math judgment.

## SANDWICH CONTEXT
[CRITICAL: LightGBM is the required MVP ranker; V4 stub only — no SASRec/GRU4Rec training/serving]
You are implementing the LightGBM ranker + eval for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: src/models/ranker.py, src/models/session_model.py, src/evaluation/evaluate.py, tests/models/test_ranker.py, tests/evaluation/test_metrics.py.
Available after: T3
Architecture rule: ranker consumes candidate features only; deterministic ordering; no V4 implementation.
[RESTATE: LightGBM is the required MVP ranker; V4 stub only — no SASRec/GRU4Rec training/serving]

## DELIVERABLE
Given 500 candidates + session features, When LightGBM ranker scores, Then Top-K ordered score desc with deterministic tie-break.
Given no baseline NDCG@10+Recall@20 for track, When challenger claims improvement, Then comparison BLOCKED until baselines exist.
Given finished evaluation, When inspected, Then NDCG@10/Recall@20/MRR@10 are 3-seed means with seeds recorded.

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - TDD; group handling correct (sum(group)=n); seeds [42,7,123]; tie-break item_id asc
  - V4 file is protocol/stub only

Must-not-have:
  - V4 training; XGBoost swap; per-dataset ranker forks
  - Library docs unavailable — LightGBM/MLflow/FastAPI docs fetched in preflight; verify API usage carefully (none flagged unknown)

Open question risks:
  - V4 interface shape assumed design-time → if wrong: NEEDS_CONTEXT (stub cheap to revise)

Rollback note: `git revert` feat commit.

## STOP CONDITIONS
Done when: DELIVERABLE passes, tests green, commit created
Escalate when: out-of-scope files touched

---

### Task 5: Training + MLflow tracking/registry + quality gate [depends: T4]

## OBJECTIVE
train.py wiring features→ranker→eval→MLflow (params/metrics/artifacts/dataset_version/git_commit, dirty-flag), registry with Champion/Challenger aliases, strict-≥ quality gate, outage queue + promotion block.

Files:
- Create: `src/training/train.py`
- Create: `src/registry/registry.py`
- Create: `src/evaluation/quality_gate.py`
- Test: `tests/training/test_quality_gate.py`
- Test: `tests/registry/test_registry.py`

Steps:
1. Write failing test for: gate PASS/FAIL/tie + outage blocks promotion + provenance present.
   File: `tests/training/test_quality_gate.py` + `tests/registry/test_registry.py`
   TDD first: tests MUST fail on greenfield repo before `src/evaluation/quality_gate.py` exists. MlflowClient is mocked — no real server.
   ```python
   # tests/training/test_quality_gate.py
   # Given champion 0.82 vs challenger 0.85 + P95 72ms + err 0.4% / When gate runs / Then PASS
   from src.evaluation.quality_gate import evaluate_gate

   def _m(ndcg, rec=0.6):
       return {"ndcg@10": ndcg, "recall@20": rec}

   def test_gate_pass():
       # Given better challenger, healthy latency/errors / When gate / Then PASS
       assert evaluate_gate(_m(0.85), _m(0.82), p95_ms=72, err_rate=0.004)["status"] == "PASS"

   def test_gate_latency_fail():
       # Given better NDCG but P95=140ms / When gate / Then FAIL, no stage change
       out = evaluate_gate(_m(0.86), _m(0.82), p95_ms=140, err_rate=0.004)
       assert out["status"] == "FAIL" and out["stage_change"] is False

   def test_gate_exact_tie_passes():
       # Given exact tie / When gate / Then PASS (strict >= semantics)
       assert evaluate_gate(_m(0.82), _m(0.82), p95_ms=100, err_rate=0.01)["status"] == "PASS"
   ```
   ```python
   # tests/registry/test_registry.py
   # Given run passing gate / When registered / Then version+linkage; outage -> queue + BLOCK
   from unittest.mock import MagicMock
   from src.registry.registry import ModelRegistry

   def test_register_links_run_before_traffic():
       # Given mocked MlflowClient / When register_model / Then create + alias called
       client = MagicMock()
       client.create_model_version.return_value.version = "3"
       reg = ModelRegistry(client=client, queue_dir="/tmp/triprank-queue")
       out = reg.register_model("HotelRanker", run_id="abc123")
       # Then
       assert out["version"] == "3" and out["run_id"] == "abc123"
       client.set_registered_model_alias.assert_called()

   def test_outage_queues_and_blocks_promotion(tmp_path):
       # Given unreachable registry / When run finishes / Then queued + BLOCKED
       from src.registry.registry import promote
       out = promote(champion="1", challenger="2", registry_ok=False, queue_dir=str(tmp_path))
       # Then
       assert out["status"] == "BLOCKED" and out["queued"] is True

   def test_train_logs_provenance(tmp_path):
       # Given finished run / When inspected / Then dataset_version + git_commit present
       from src.training.train import run_training
       logged = {}
       fake_client = MagicMock()
       fake_client.log_param.side_effect = lambda k, v: logged.update({k: v})
       out = run_training(dataset_version="v2026.09.13", client=fake_client, queue_dir=str(tmp_path))
       # Then
       assert "dataset_version" in logged and "git_commit" in logged and out["run_id"]
   ```
2. Run test — verify FAIL: `pytest tests/training tests/registry -x -q`
3. Implement: train() logs full provenance (dataset_version, git_commit + dirty flag); registry wrapper (create_registered_model HotelRanker, create_model_version, set alias Champion/Challenger via MlflowClient, local queue dir on outage); quality_gate.evaluate(challenger, champion, p95, err) strict ≥ ties PASS.
4. Run test — verify PASS: `pytest tests/training tests/registry -q`
5. Refactor while green; re-run — must stay PASS.
6. Commit: `git add src/training src/registry src/evaluation/quality_gate.py tests/training tests/registry`; `git commit -m "feat(mlops): training mlflow registry quality-gate"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rules: Tracking/registry (S5), Quality gate (S6); MLflow docs (aliases, stages).
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: standard
Justification: 3 source files, registry + gate judgment, outage semantics.

## SANDWICH CONTEXT
[CRITICAL: Native MLflow Registry stages + Champion/Challenger aliases; outage → queue locally + BLOCK promotion; gate strict ≥ ties PASS]
You are implementing training + registry + gate for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: src/training/train.py, src/registry/registry.py, src/evaluation/quality_gate.py, tests/training/test_quality_gate.py, tests/registry/test_registry.py.
Available after: T4 (parallel with T6)
Architecture rule: no custom registry DB; provenance mandatory.
[RESTATE: Native MLflow Registry stages + Champion/Challenger aliases; outage → queue locally + BLOCK promotion; gate strict ≥ ties PASS]

## DELIVERABLE
Given finished run, When inspected in MLflow, Then params, NDCG@10, Recall@20, artifacts, dataset_version, git_commit present (dirty flagged).
Given run passing gate, When registered as HotelRanker, Then version + stage + run linkage exist before traffic.
Given MLflow/Registry unreachable, When run finishes, Then payload queued locally with retry; promotion BLOCKED.
Given champion 0.82 vs challenger 0.85 + P95 72ms + err 0.4%, When gate runs, Then PASS; Given P95 140ms Then FAIL no stage change; Given exact tie Then PASS (metric leg).

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - TDD; mocks for MlflowClient (no real server in unit tests); conventional commit

Must-not-have:
  - Custom registry service; silent dirty-git logging; proceeding without logging

Open question risks: none

Rollback note: registry stage demotion is metadata-only revert.

## STOP CONDITIONS
Done when: DELIVERABLE passes, tests green, commit created
Escalate when: out-of-scope files touched

---

### Task 6: FastAPI recommend + health/ready + fallback + trace [depends: T4]

## OBJECTIVE
Versioned API: POST /v1/recommend (happy/cold-start/fallback/short/empty/422), GET /health + /ready with Redis-gated readiness, edge P95 tracking, trace fields.

Files:
- Create: `api/main.py`
- Create: `src/models/inference.py`
- Test: `tests/api/test_recommend.py`

Steps:
1. Write failing test for: happy ranking + cold-start + corrupt fallback + 422 + health/ready split + trace fields.
   File: `tests/api/test_recommend.py`
   TDD first: tests MUST fail on greenfield repo before `api/main.py` exists. TestClient only; Redis/model via fakes.
   ```python
   # tests/api/test_recommend.py
   # Given session with state / When POST /v1/recommend / Then <=20 ordered + version + request_id
   from unittest.mock import MagicMock
   from fastapi.testclient import TestClient
   import api.main as main

   def _client(**kw):
       store = kw.pop("store", {"trivago:S123": {"recent_items": ["H10", "H21"]}})
       ranker = MagicMock()
       ranker.recommend.side_effect = lambda sid, cands, k=20: cands[:k]
       app = main.create_app(session_store=store, ranker=ranker, **kw)
       return TestClient(app)

   def test_happy_ranking_has_trace_fields():
       # Given stored session / When POST / Then ordered + model_version + request_id
       r = _client().post("/v1/recommend", json={"session_id": "S123", "track": "trivago"})
       assert r.status_code == 200
       body = r.json()
       assert len(body["items"]) <= 20 and body["model_version"] and body["request_id"]

   def test_cold_start_unknown_session():
       # Given unknown/expired session / When POST / Then 200 baseline-popularity
       r = _client(store={}).post("/v1/recommend", json={"session_id": "S999"})
       assert r.status_code == 200 and r.json()["model_version"] == "baseline-popularity"

   def test_corrupt_artifact_fallback_200():
       # Given corrupt artifact / When POST / Then 200 fallback (never 5xx)
       c = _client(model_ok=False)
       r = c.post("/v1/recommend", json={"session_id": "S123"})
       assert r.status_code == 200 and r.json()["model_version"] == "fallback"

   def test_missing_session_id_422():
       # Given body {} / When POST / Then 422
       assert _client().post("/v1/recommend", json={}).status_code == 422

   def test_short_and_empty_lists():
       # Given 0<n<K / When POST / Then exactly n; Given 0 everywhere / Then empty + reason
       c = _client(store={"trivago:S1": {"recent_items": []}}, inventory=["Hx"])
       assert len(c.post("/v1/recommend", json={"session_id": "S1"}).json()["items"]) == 1
       c0 = _client(store={}, inventory=[])
       r0 = c0.post("/v1/recommend", json={"session_id": "S0"})
       assert r0.json()["items"] == [] and r0.json()["reason"] == "no_candidates"

   def test_health_ready_split():
       # Given Redis down / When probed / Then /health 200 + /ready 503
       c = _client(redis_ok=False)
       assert c.get("/health").status_code == 200
       assert c.get("/ready").status_code == 503
   ```
2. Run test — verify FAIL: `pytest tests/api -x -q`
3. Implement: FastAPI app with TestClient-testable routes; request_id middleware; P95 tracker (trailing 1000 server-time); model loader with fallback (model_version=fallback + ERROR log); popularity fallback (baseline-popularity); empty → reason=no_candidates; 422 on missing session_id (model_version=none in logs); /health 200 always; /ready 503 when Redis/model unavailable.
4. Run test — verify PASS: `pytest tests/api -q`
5. Refactor while green; re-run — must stay PASS.
6. Commit: `git add api/main.py src/models/inference.py tests/api`; `git commit -m "feat(api): recommend health ready fallback trace"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rules: Ranked response (S1), Reliability (S10); FastAPI docs (TestClient, validation errors).
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: standard
Justification: 2 source files but 6+ GWT paths + P95 + readiness judgment.

## SANDWICH CONTEXT
[CRITICAL: Graceful degradation — never 5xx on model failure; P95 edge trailing-1000; trace fields on every response/log]
You are implementing the serving API for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: api/main.py, src/models/inference.py, tests/api/test_recommend.py.
Available after: T4 (parallel with T5)
Architecture rule: 422 keeps request_id + model_version=none; corrupt artifact → 200 fallback; /ready reflects Redis+model.
[RESTATE: Graceful degradation — never 5xx on model failure; P95 edge trailing-1000; trace fields on every response/log]

## DELIVERABLE
Given session with state, When POST /v1/recommend, Then ≤20 ordered + model_version + request_id, latency counted to P95.
Given unknown/expired session, When POST, Then 200 popularity model_version=baseline-popularity.
Given corrupt artifact, When POST, Then 200 fallback + ERROR log (request_id + expected version).
Given 0<n<K, When POST, Then exactly n items. Given 0 everywhere, When POST, Then 200 empty + reason=no_candidates.
Given body {}, When POST, Then 422.
Given Redis down, When probed, Then /health 200 + /ready 503.
Given any call, When response/logs inspected, Then request_id + session/model_version + latency present.

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - TDD with TestClient; pytest-asyncio where async; fakeredis/mock for Redis in unit tests

Must-not-have:
  - 5xx on model failure; 404 on empty; padding short lists; real Kafka/Redis required in unit tests

Open question risks:
  - Q1 assumed ML-gates rule → if wrong: NEEDS_CONTEXT (SLA promotion blocks would reshape API metrics)

Rollback note: `docker compose up <prev>` image; alias revert.

## STOP CONDITIONS
Done when: DELIVERABLE passes, tests green, commit created
Escalate when: out-of-scope files touched

---

### Task 7: Streaming producer/consumer + session processor (Kafka→Redis) [depends: T2]

## OBJECTIVE
Real Kafka producer/consumer + session processor: timestamp authority, per-key serialization, atomic Redis writes, idempotent duplicates, 30-min sliding TTL.

Files:
- Create: `src/streaming/producer.py`
- Create: `src/streaming/consumer.py`
- Create: `src/streaming/session_processor.py`
- Test: `tests/streaming/test_session_processor.py`

Steps:
1. Write failing test for: click update + duplicate idempotent + stale ignored + TTL expiry path (fakeredis/mock kafka).
   File: `tests/streaming/test_session_processor.py`
   TDD first: tests MUST fail on greenfield repo before `src/streaming` exists. fakeredis/in-memory double only — no real broker.
   ```python
   # tests/streaming/test_session_processor.py
   # Given Redis recent_items=[H10,H21] last_ts=T / When click H33 ts=T+1 / Then atomic state
   from src.streaming.session_processor import SessionProcessor

   class FakeRedis:
       def __init__(self): self.store, self.ttls = {}, {}
       def pipeline(self): return self
       def __enter__(self): return self
       def __exit__(self, *a): self._flush(); return False
       def _flush(self):
           for op in getattr(self, "_ops", []): op()
           self._ops = []
       def execute(self): self._flush()
       def hset(self, k, mapping):
           def _op(): self.store.setdefault(k, {}).update(mapping)
           getattr(self, "_ops", self.__dict__.setdefault("_ops", [])).append(_op)
       def expire(self, k, s): self.ttls[k] = s
       def hgetall(self, k): return self.store.get(k, {})

   def _proc():
       return SessionProcessor(redis_client=FakeRedis(), ttl_seconds=1800)

   def _evt(eid="evt_999", ts=101, item="H33", typ="click"):
       return {"event_id": eid, "session_id": "trivago:S123",
               "timestamp": ts, "item_id": item, "event_type": typ}

   def test_click_updates_state_atomically():
       # Given last_ts=T / When ts=T+1 click / Then H33 + last_event + last_ts
       p = _proc()
       p.apply_event(_evt(ts=100, item="H10")); p.apply_event(_evt(eid="e2", ts=101, item="H33"))
       # Then
       st = p.get_state("trivago:S123")
       assert "H33" in st["recent_items"] and st["last_ts"] == 101
       assert p.redis.ttls["trivago:S123"] == 1800  # sliding TTL refreshed

   def test_duplicate_redelivery_idempotent():
       # Given evt applied / When redelivered / Then unchanged
       p = _proc()
       p.apply_event(_evt()); before = p.get_state("trivago:S123")
       p.apply_event(_evt())
       assert p.get_state("trivago:S123") == before

   def test_stale_event_ignored():
       # Given last_ts=T+5 / When ts=T+2 arrives / Then ignored
       p = _proc()
       p.apply_event(_evt(ts=105, item="H21"))
       p.apply_event(_evt(eid="stale", ts=102, item="H99"))
       st = p.get_state("trivago:S123")
       assert st["last_ts"] == 105 and "H99" not in st["recent_items"]
   ```
2. Run test — verify FAIL: `pytest tests/streaming -x -q`
3. Implement: processor.apply_event with last_ts compare, per-key lock, atomic write (single pipeline/LUA: recent_items+city+filters+last_event+last_ts), TTL 30min sliding refresh, duplicate event_id set.
4. Run test — verify PASS: `pytest tests/streaming -q`
5. Refactor while green; re-run — must stay PASS.
6. Commit: `git add src/streaming tests/streaming`; `git commit -m "feat(streaming): kafka processor redis atomic state"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rule: Session state (S2: click/duplicate/stale/namespace).
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: standard
Justification: 3 source files, ordering/concurrency/atomicity judgment; mocks keep it unit-testable.

## SANDWICH CONTEXT
[CRITICAL: Timestamp authority (stale ignored); atomic per-session writes; 30-min sliding TTL; duplicate event_ids single-apply]
You are implementing streaming session state for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar (real Kafka+Redis in compose).
Files in scope: src/streaming/producer.py, src/streaming/consumer.py, src/streaming/session_processor.py, tests/streaming/test_session_processor.py.
Available after: T2 (parallel with T3)
Architecture rule: unit tests use fakes/mocks — real Kafka/Redis only in compose/integration.
[RESTATE: Timestamp authority (stale ignored); atomic per-session writes; 30-min sliding TTL; duplicate event_ids single-apply]

## DELIVERABLE
Given Redis recent_items=[H10,H21] last_ts=T, When evt_999 click H33 ts=T+1 flows, Then atomic state includes H33, last_event=click, last_ts=T+1.
Given evt_123 applied, When redelivered, Then unchanged.
Given last_ts=T+5, When ts=T+2 arrives, Then ignored.
Given TTL expired, When recommend reads, Then cold-start path (jointly verified T6).

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - TDD; no real broker in unit tests; per-key serialization documented

Must-not-have:
  - Arrival-order-wins; partial writes; real infra dependency in unit tests

Open question risks: none

Rollback note: consumer group reset + Redis key expiry.

## STOP CONDITIONS
Done when: DELIVERABLE passes, tests green, commit created
Escalate when: out-of-scope files touched

---

### Task 8: Canary ladder + auto-rollback + drift/retrain triggers [depends: T5, T6]

## OBJECTIVE
Step-gated canary 95/5→75/25→50/50→0/100 over 500-req windows + rollback on 5xx>2%/P95>200ms; PSI-band drift + NDCG-drop triggers with 24h debounce.

Files:
- Create: `src/deployment/canary.py`
- Create: `src/monitoring/drift.py`
- Test: `tests/deployment/test_canary.py`
- Test: `tests/monitoring/test_drift.py`

Steps:
1. Write failing test for: advance on green + error rollback + latency rollback + PSI>0.25 fires + debounce suppresses + NDCG drop fires.
   File: `tests/deployment/test_canary.py`, `tests/monitoring/test_drift.py`
   TDD first: tests MUST fail on greenfield repo before `src/deployment/canary.py` / `src/monitoring/drift.py` exist. Injectable clock for debounce.
   ```python
   # tests/deployment/test_canary.py
   # Given 95/5 green (5xx<=1%, P95<=100ms/500) / When gate / Then advance to 75/25
   from src.deployment.canary import evaluate_step

   def test_advance_on_green():
       # Given green window / When gate / Then next ladder step
       out = evaluate_step(current="95/5", err_rate=0.008, p95_ms=90, window=500)
       assert out["next"] == "75/25"

   def test_error_breach_rolls_back():
       # Given 5xx 2.6%/trailing-500 / When evaluated / Then 100% champion
       out = evaluate_step(current="75/25", err_rate=0.026, p95_ms=80, window=500)
       assert out["next"] == "100/0" and out["challenger"] == "unhealthy"

   def test_latency_breach_rolls_back():
       # Given P95>200ms / When evaluated / Then 100% champion
       out = evaluate_step(current="50/50", err_rate=0.005, p95_ms=250, window=500)
       assert out["next"] == "100/0"
   ```
   ```python
   # tests/monitoring/test_drift.py
   # Given PSI=0.31 / When drift runs / Then RETRAIN RECOMMENDED (debounced 24h)
   from src.monitoring.drift import check_drift, check_performance_drop

   def test_psi_over_threshold_fires():
       # Given significant drift / When job runs / Then trigger names feature + PSI
       out = check_drift({"hotel_price": 0.31}, store={})
       assert out["status"] == "RETRAIN RECOMMENDED" and out["psi"] == 0.31

   def test_debounce_suppresses_repeat_within_24h():
       # Given same trigger fired <24h ago / When re-run / Then suppressed
       store = {}
       check_drift({"hotel_price": 0.31}, store=store, now=0)
       out = check_drift({"hotel_price": 0.31}, store=store, now=3600)
       assert out["status"] == "SUPPRESSED"

   def test_ndcg_drop_fires_with_both_values():
       # Given train 0.82 vs prod 0.74 / When evaluated / Then trigger + debounce
       out = check_performance_drop(train_ndcg=0.82, prod_ndcg=0.74, store={})
       assert out["status"] == "RETRAIN RECOMMENDED" and out["prod_ndcg"] == 0.74
   ```
2. Run test — verify FAIL: `pytest tests/deployment tests/monitoring -x -q`
3. Implement: canary step evaluator (window=500, advance iff 5xx≤1% and P95≤100ms; rollback to 100% champion iff 5xx>2% or P95>200ms trailing 500); drift PSI with bands <0.10/0.10–0.25/>0.25 + KS secondary; trigger store with 24h per-type debounce.
4. Run test — verify PASS: `pytest tests/deployment tests/monitoring -q`
5. Refactor while green; re-run — must stay PASS.
6. Commit: `git add src/deployment src/monitoring/drift.py tests/deployment tests/monitoring`; `git commit -m "feat(deploy): canary rollback drift retrain"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rules: Canary/rollback (S7), Drift/retrain (S8).
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: standard
Justification: 2 source files, window/threshold/debounce judgment across deploy + monitoring.

## SANDWICH CONTEXT
[CRITICAL: Every canary step gated on 500-req window; rollback 5xx>2% or P95>200ms trailing-500; retrain debounce 24h per type]
You are implementing canary + drift for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: src/deployment/canary.py, src/monitoring/drift.py, tests/deployment/test_canary.py, tests/monitoring/test_drift.py.
Available after: T5, T6
Architecture rule: gate (err≤1%) vs canary-rollback (>2%) are intentionally different stages — document both, keep metric definitions identical.
[RESTATE: Every canary step gated on 500-req window; rollback 5xx>2% or P95>200ms trailing-500; retrain debounce 24h per type]

## DELIVERABLE
Given 95/5 green (5xx≤1%, P95≤100ms/500), When step gate runs, Then advance to 75/25.
Given 5xx 2.6%/trailing-500, When evaluated, Then 100% champion + challenger unhealthy.
Given P95>200ms/trailing-500 any step, When evaluated, Then 100% champion.
Given PSI=0.31, When drift runs, Then RETRAIN RECOMMENDED + trigger (suppressed if fired <24h ago).
Given train 0.82 vs prod 0.74, When evaluated, Then retrain trigger with both values (same debounce).

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - TDD; window sizes as named constants; debounce timestamps persisted/injectable clock

Must-not-have:
  - Time-based auto-advance without health; per-step manual approval; undebounced storm triggers

Open question risks: none

Rollback note: alias Champion → previous version; trigger log audit.

## STOP CONDITIONS
Done when: DELIVERABLE passes, tests green, commit created
Escalate when: out-of-scope files touched

---

### Task 9: Metrics instrumentation + Prometheus/Grafana [depends: T6]

## OBJECTIVE
prometheus-client instrumentation (RPS, P50/P95/P99, error rate, per-model_version latency, prediction/drift gauges) + prometheus.yml + Grafana dashboard (system + ML + business-proxy).

Files:
- Create: `src/monitoring/metrics.py`
- Create: `monitoring/prometheus.yml`
- Create: `monitoring/grafana/dashboard.json`
- Test: `tests/monitoring/test_metrics.py`

Steps:
1. Write failing test for: request counting + latency observe + error counting + version label split.
   File: `tests/monitoring/test_metrics.py`
   TDD first: tests MUST fail on greenfield repo before `src/monitoring/metrics.py` exists. Uses a fresh CollectorRegistry per test — no global state leakage.
   ```python
   # tests/monitoring/test_metrics.py
   # Given recommend traffic / When scraped / Then RPS + P50/P95/P99 + error + per-version latency
   from prometheus_client import CollectorRegistry, generate_latest
   from src.monitoring.metrics import Metrics

   def test_request_counting():
       # Given 3 requests / When recorded / Then counter == 3
       m = Metrics(CollectorRegistry())
       for _ in range(3): m.observe_request("ranker-v3", 0.02, ok=True)
       assert generate_latest(m.registry).count(b"triprank_requests_total")

   def test_latency_observe_and_error_counting():
       # Given latencies + 1 error / When observed / Then histogram + error counter present
       m = Metrics(CollectorRegistry())
       m.observe_request("ranker-v3", 0.05, ok=True)
       m.observe_request("ranker-v3", 0.01, ok=False)
       blob = generate_latest(m.registry)
       assert b"triprank_latency_seconds" in blob and b"triprank_errors_total" in blob

   def test_version_label_split():
       # Given two model versions / When observed / Then per-version series exist
       m = Metrics(CollectorRegistry())
       m.observe_request("ranker-v3", 0.02, ok=True)
       m.observe_request("baseline-popularity", 0.01, ok=True)
       blob = generate_latest(m.registry).decode()
       assert 'model_version="ranker-v3"' in blob
       assert 'model_version="baseline-popularity"' in blob
   ```
2. Run test — verify FAIL: `pytest tests/monitoring/test_metrics.py -x -q`
3. Implement: counters/histograms/gauges with model_version label; middleware hook; dashboard JSON with system + ML + business-proxy panels.
4. Run test — verify PASS: `pytest tests/monitoring -q`
5. Refactor while green; re-run — must stay PASS.
6. Commit: `git add src/monitoring/metrics.py monitoring tests/monitoring/test_metrics.py`; `git commit -m "feat(monitoring): prometheus metrics grafana dashboard"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — rule: Monitoring (S8/S10); brief §12 panel groups.
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: lightweight
Justification: 1 source file + 2 config files, commodity instrumentation.

## SANDWICH CONTEXT
[CRITICAL: P95 definition identical to gate/canary (edge, trailing-1000); per-model_version latency split]
You are implementing observability for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: src/monitoring/metrics.py, monitoring/prometheus.yml, monitoring/grafana/dashboard.json, tests/monitoring/test_metrics.py.
Available after: T6
Architecture rule: commodity prom-client, no hand-rolled metrics.
[RESTATE: P95 definition identical to gate/canary (edge, trailing-1000); per-model_version latency split]

## DELIVERABLE
Given recommend traffic, When scraped, Then RPS + P50/P95/P99 + error rate + per-version latency present.
Given dashboard import, When viewed, Then system + ML + business-proxy panels render (per brief §12).

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - TDD for instrumentation; dashboard JSON valid JSON

Must-not-have:
  - Hand-rolled metrics server; dashboard scope beyond brief §12 without approval

Open question risks:
  - Grafana panel set assumed §12 → if wrong: DONE_WITH_CONCERNS + note

Rollback note: revert commit; dashboard re-import.

## STOP CONDITIONS
Done when: DELIVERABLE passes, tests green, commit created
Escalate when: out-of-scope files touched

---

### Task 10: Compose services + CI gates + docs + portfolio UI [depends: T6, T7]

## OBJECTIVE
Full docker-compose (api, mlflow, kafka, redis, prometheus, grafana), training/streaming Dockerfiles, model-validation workflow, architecture/ml-pipeline/deployment/monitoring docs, minimal portfolio UI (recommendation + MLOps pages).

Files:
- Modify: `docker-compose.yml`
- Create: `docker/Dockerfile.training`
- Create: `docker/Dockerfile.streaming`
- Create: `.github/workflows/model-validation.yml`
- Create: `docs/architecture.md`
- Create: `docs/ml-pipeline.md`
- Create: `docs/deployment.md`
- Create: `docs/monitoring.md`
- Create: `ui/app.py`

Steps:
1. Create the structure/files (non-testable ops/docs/UI task).
2. Verify: `docker compose config` + `python -m py_compile ui/app.py` + `ls docs/*.md` + CI yaml parse (`python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/model-validation.yml'))"` or visual check if pyyaml absent).
3. Commit: `git add docker-compose.yml docker .github docs ui`; `git commit -m "chore(release): compose docs ui validation-workflow"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — scope Phase 6 + docs list + portfolio UI §19–20.
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: lightweight
Justification: ops/docs/UI assembly, no branching logic; verification is config-parse + compile.

## SANDWICH CONTEXT
[CRITICAL: One-command `docker compose up` mini-production; GCP path documented, no cloud spend]
You are implementing release assembly for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: docker-compose.yml, docker/Dockerfile.training, docker/Dockerfile.streaming, .github/workflows/model-validation.yml, docs/architecture.md, docs/ml-pipeline.md, docs/deployment.md, docs/monitoring.md, ui/app.py.
Available after: T6, T7
Architecture rule: local Kafka/Redis map to Pub/Sub + Memorystore in docs; Cloud Run/GKE path noted.
[RESTATE: One-command `docker compose up` mini-production; GCP path documented, no cloud spend]

## DELIVERABLE
Verification — DONE when: compose config parses with all 6 services; training + streaming images build (or Dockerfiles lint-clean if daemon absent); model-validation workflow gates NDCG/P95/coverage; 4 docs exist; ui/app.py compiles and shows recommendation + MLOps pages.

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - [no-tdd — structural task]; pinned image tags; quality-gate thresholds match spec (NDCG≥champion, P95≤100ms, err≤1%)

Must-not-have:
  - Real cloud provisioning; live traffic; V4 serving

Open question risks: none

Rollback note: `docker compose down && docker compose up <prev>`.

## STOP CONDITIONS
Done when: verifications pass, commit created
Escalate when: out-of-scope files touched

---

### Task 11: E2E integration (adapter→rank→api→canary) [depends: T6, T7, T8]

## OBJECTIVE
End-to-end proof: synthetic Trivago + OTTO events → canonical → features → candidates → rank → API (TestClient + fakes) → canary advance + rollback paths.

Files:
- Test: `tests/integration/test_e2e.py`

Steps:
1. Write failing integration test for: dual-track ingest → recommend ordered + versioned → canary green advance → breach rollback → README runbook snippet.
   File: `tests/integration/test_e2e.py`
   TDD first: tests MUST fail on greenfield repo before the pipeline exists. Fakes/mocks only (no real Kafka/Redis/MLflow). No new tasks added — T11 already covers e2e.
   ```python
   # tests/integration/test_e2e.py
   # Given synthetic Trivago + OTTO events / When pipeline + API run
   # Then ordered versioned recommendations for both tracks
   from unittest.mock import MagicMock
   from fastapi.testclient import TestClient
   import api.main as main
   from src.data.adapters.otto import normalize_otto
   from src.data.adapters.trivago import normalize_trivago
   from src.deployment.canary import evaluate_step
   from src.streaming.session_processor import SessionProcessor

   class MemRedis:
       def __init__(self): self.store = {}
       def pipeline(self): return self
       def __enter__(self): return self
       def __exit__(self, *a): return False
       def execute(self): pass
       def hset(self, k, mapping): self.store.setdefault(k, {}).update(mapping)
       def expire(self, k, s): pass
       def hgetall(self, k): return self.store.get(k, {})

   def _ingest(proc):
       # Given one event per track / When normalized + applied / Then dual-track state
       t = normalize_trivago({"session_id": "S1", "item_id": "H10", "timestamp": 1757760000,
                              "event_type": "click", "city": "Bali"})
       o = normalize_otto({"session_id": "s1", "order_id": "a1", "item_id": "a1",
                           "timestamp": 1757760000, "event_type": "order"})
       proc.apply_event(t.__dict__); proc.apply_event(o.__dict__)
       assert t.session_id == "trivago:S1" and o.session_id == "otto:s1"

   def test_dual_track_ingest_recommend_canary():
       # Given dual-track ingest / When recommend + canary gate
       proc = SessionProcessor(redis_client=MemRedis(), ttl_seconds=1800)
       _ingest(proc)
       store = {"trivago:S1": proc.get_state("trivago:S1"),
                "otto:s1": proc.get_state("otto:s1")}
       app = main.create_app(session_store=store, ranker=MagicMock())
       c = TestClient(app)
       # Then ordered versioned recommendations for both tracks
       for sid, track in [("S1", "trivago"), ("s1", "otto")]:
           r = c.post("/v1/recommend", json={"session_id": sid, "track": track})
           assert r.status_code == 200 and r.json()["request_id"]
       # Given canary green window / When gate / Then advance
       assert evaluate_step("95/5", 0.005, 80, 500)["next"] == "75/25"
       # Given breach / When evaluated / Then rollback
       assert evaluate_step("75/25", 0.03, 80, 500)["next"] == "100/0"
   ```
2. Run test — verify FAIL: `pytest tests/integration -x -q`
3. Wire minimal glue only if test demands (no new prod logic beyond small test fixtures; prod fixes go to owning tasks).
4. Run test — verify PASS: `pytest tests/integration -q`
5. Refactor while green (test-only); re-run — must stay PASS.
6. Commit: `git add tests/integration`; `git commit -m "test(e2e): dual-track recommend canary paths"`

## REFERENCES LOADED
docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md — full acceptance criteria; preflight fakes-only integration rule.
[CRITICAL: Without this section, packet is incomplete]

## WHY THIS APPROACH
Complexity: standard
Justification: multi-unit orchestration judgment; test-only code.

## SANDWICH CONTEXT
[CRITICAL: No real Kafka/Redis/MLflow in tests — fakes/mocks only; full stack verified via compose manually]
You are implementing E2E integration proof for TripRank.
Spec: docs/pocket/spec/2026-09-13-triprank-platform/triprank-full-platform.md
Design decision: Option A modular monolith + streaming sidecar.
Files in scope: tests/integration/test_e2e.py (+ tiny fixtures).
Available after: T6, T7, T8
Architecture rule: integration failures caused by unit bugs → fix owning task, not here.
[RESTATE: No real Kafka/Redis/MLflow in tests — fakes/mocks only; full stack verified via compose manually]

## DELIVERABLE
Given synthetic Trivago + OTTO events, When pipeline + API run, Then ordered versioned recommendations for both tracks.
Given canary green window, When step gate runs, Then advance; Given breach, When evaluated, Then rollback — both exercised through public interfaces.

Format: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

## QUALITY BAR
Must-have:
  - TDD; public-interface only (no privates); both tracks exercised

Must-not-have:
  - Real external services; duplicated unit coverage; new prod scope

Open question risks: none

Rollback note: revert test commit only.

## STOP CONDITIONS
Done when: DELIVERABLE passes, tests green, commit created
Escalate when: requires prod changes beyond fixtures (route to owning task)

---

## Plan Summary

| Task | Name | Depends | Complexity | Key Verification |
|------|------|---------|------------|-----------------|
| T1 | Scaffold repo/manifests/compose/CI | prereq | lightweight | install + collect-only + compose config |
| T2 | Schema + adapters + validation | T1 | standard | null-context valid, namespaces isolated, quarantine |
| T3 | Features + candidates + baselines | T2 | standard | ≤500 retrieval, global fallback, short passthrough |
| T4 | LightGBM ranker + eval + V4 stub | T3 | standard | ordered Top-K, baseline-first, 3-seed means |
| T5 | Training + MLflow + registry + gate | T4 | standard | provenance, queued outage, strict-≥ gate |
| T6 | FastAPI + fallback + trace | T4 | standard | 200 paths + 422 + health/ready + P95 |
| T7 | Streaming processor Kafka→Redis | T2 | standard | atomic ordered idempotent + TTL |
| T8 | Canary + rollback + drift triggers | T5, T6 | standard | gated advance, dual rollback, debounced retrain |
| T9 | Metrics + Prometheus + Grafana | T6 | lightweight | per-version latency + 3-panel dashboard |
| T10 | Compose + CI + docs + UI | T6, T7 | lightweight | one-command up + docs + compiling UI |
| T11 | E2E integration dual-track | T6, T7, T8 | standard | ingest→recommend→canary green + rollback |
