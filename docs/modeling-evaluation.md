# Modeling & Evaluation

> Training code: `src/training/`; models: `src/models/`; eval:
> `src/evaluation/`. Production run: `e8892480` on docker MLflow
> (`http://localhost:5000`), registry `TripRanker` v1 = Champion.

## 1. Training entrypoints

| Script | Input | Output | When to use |
|---|---|---|---|
| `python -m src.training.train_real [--sessions 200000] [--holdout-days 7] [--tracking-uri URI]` | RetailRocket `events.csv` | MLflow run + `artifacts/ranker-retailrocket-v1/` + Champion registration | full retrain from the base dataset |
| `powershell -ExecutionPolicy Bypass -File scripts/retrain_docker.ps1` (`$env:SESSIONS`, `$env:HOLDOUT_DAYS`) | same | same, tracking forced to docker MLflow | one-command retrain (sets `MLFLOW_TRACKING_URI`, UTF-8 stdout) |
| `python scripts/retrain_from_app.py [--min-app-events 100] [--out-dir artifacts/...] [--check-only]` | base CSV **+** `events_app` live rows (mapped back to view/addtocart/transaction) | `artifacts/ranker-retailrocket-v2/` on gate PASS; **never overwrites Champion** | MLOps cycle retrain once live traffic ≥ threshold |

Tracking-URI resolution (`resolve_tracking_uri`): `--tracking-uri` flag >
`MLFLOW_TRACKING_URI` env > live probe of docker `:5000` > local sqlite
fallback. Every run logs: hyperparams + `dataset_version`
(`retailrocket-hf@<csv-length-hash>`) + `git_commit` + dirty flag as params;
NDCG@10 / Recall@20 / MRR@10 / baseline-NDCG as metrics; `model.pkl`,
`meta.json`, `popularity.csv` under artifact path `model/`.

## 2. Holdout protocol (time-based, no leakage)

`split_time_holdout`: cutoff = `max(timestamp) − holdout_days × 86400 × 1000`;
everything before → train, everything at/after → holdout (default 7 days).
Popularity baseline is built from **train only** and evaluated on holdout
queries — the honest comparison. Train uses up to `--sessions` sessions;
holdout uses `sessions // 4`.

## 3. Optimizer & objective

`LGBMRanker(objective="lambdarank", n_estimators=100, num_leaves=31,
lambdarank_truncation_level=10)` — pairwise/listwise gradient method that
directly optimizes truncated NDCG@10 rather than pointwise error.
Group sizes = per-session candidate counts (`group=`). Deterministic
negatives (seed 42); metrics averaged over seeds [42, 7, 123]
(`src/evaluation/evaluate.py::SEEDS` — currently the same ranking is
re-scored per seed, so the mean is exact, not stochastic).

## 4. Metrics (definitions in `src/evaluation/evaluate.py`)

- **NDCG@10**: rank-discounted gain over binary relevance (converted=1),
  normalized per query. Primary metric — position-sensitive, matches UX.
- **Recall@20**: fraction of converted items retrieved in top-20. Coverage.
- **MRR@10**: reciprocal rank of the first hit. "How far must the user scroll."

Production holdout numbers (from `meta.json`, run `e8892480`):

| Metric | ranker-retailrocket-v1 | popularity baseline | Lift |
|---|---|---|---|
| NDCG@10 | **0.9777** | 0.7274 | +0.250 (+34%) |
| Recall@20 | 0.9947 | 0.9656 | +0.029 |
| MRR@10 | 0.9727 | 0.6429 | +0.330 |

## 5. Quality gate (`src/evaluation/quality_gate.py::evaluate_gate`)

Strict-≥ on the two ranking legs, ceilings on ops legs — ties PASS:

- `ndcg@10 ≥ champion`, `recall@20 ≥ champion`
- `P95 ≤ 100 ms` (`P95_MAX_MS`), `error ≤ 1%` (`ERR_MAX`)

`train_real` raises `SystemExit` on FAIL — a failed model never reaches the
registry. Current gate: **PASS** (NDCG 0.9777 ≥ 0.7274, recall 0.9947 ≥
0.9656, P95 ≈ 2.7 ms, error 0).

## 6. Registry & promotion (`src/registry/registry.py`)

- `ModelRegistry.register_model(name, run_id, alias="Challenger")`:
  create-if-missing → version from `runs:/<id>/model` → set alias.
  `train_real` registers straight to **`Champion`**.
- `promote(name, version)`: moves the `Champion` alias (manual rollback =
  re-point the alias, no redeploy).
- Outage path (`promote()` function): when the registry is unreachable,
  the promotion payload is queued to `/tmp/triprank-queue/` and status is
  `BLOCKED` — never silently skipped.

## 7. Known MLflow hosting quirk (must-read before operating)

The docker MLflow server was started with a **bare absolute**
`--default-artifact-root /mlflow/artifacts`. Host-side clients resolve that
URI as a *local* path, so `log_artifact` from Windows writes to
`D:\mlflow\artifacts\...` while the server sees nothing (REST
`artifacts/list` empty, no error). Recovery used: `docker cp` the host-side
files into the container path. For future retrains, either set the artifact
root to an S3-style/proxied URI or always run the log step from inside the
compose network. The fluent `MlflowClient.log_artifact` signature is
`(run_id, local_path, artifact_path)` — the `(path, artifact_path)` call
shape in `src/training/train.py`'s client branch is wrong for real clients
(the shipped retrain used the no-client/prod branch, which is correct).
