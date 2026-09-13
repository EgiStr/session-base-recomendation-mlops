"""Training entrypoint: features → ranker → eval → MLflow with full provenance."""
from __future__ import annotations

import subprocess
import uuid
from typing import Any, Dict, Mapping, Sequence


def _git_commit() -> tuple[str, bool]:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, timeout=5)
        commit = out.stdout.strip() if out.returncode == 0 else "unknown"
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                               text=True, timeout=5)
        return commit, bool(dirty.stdout.strip())
    except Exception:
        return "unknown", False


def run_training(dataset_version: str, client: Any = None,
                 queue_dir: str = "/tmp/triprank-queue",
                 params: Dict[str, Any] | None = None,
                 metrics: Mapping[str, float] | None = None,
                 artifacts: Sequence[str] | None = None,
                 artifact_path: str | None = None) -> Dict[str, Any]:
    commit, dirty = _git_commit()
    run_id = uuid.uuid4().hex[:12]
    provenance = {"dataset_version": dataset_version, "git_commit": commit,
                  "git_dirty": dirty, "run_id": run_id}
    if client is not None:  # injected fake in tests; real mlflow client in prod
        for k, v in {**(params or {}), **provenance}.items():
            client.log_param(k, v)
        for k, v in (metrics or {}).items():
            client.log_metric(k, float(v))
        for path in artifacts or []:
            if hasattr(client, "log_artifact"):
                try:
                    from mlflow.tracking import MlflowClient as _MlflowClient
                except Exception:
                    _MlflowClient = None
                if _MlflowClient is not None and isinstance(client, _MlflowClient):
                    # Real MlflowClient: log_artifact(run_id, local_path, ...).
                    client.log_artifact(run_id, path, artifact_path)
                else:
                    # Fluent mlflow module or test fake: log_artifact(local_path, ...).
                    # NOTE: when the tracking server's artifact root is a bare
                    # absolute path (e.g. /mlflow/artifacts), a Windows host-side
                    # client resolves it as a LOCAL path and uploads land on the
                    # host, invisible to the server REST API — copy them into the
                    # server container (or use an mlflow-artifacts proxied URI).
                    client.log_artifact(path, artifact_path)
    else:  # pragma: no cover - prod path needs a live tracking server
        import mlflow
        with mlflow.start_run(run_name=f"triprank-{run_id}") as run:
            mlflow.log_params({**(params or {}), **provenance})
            if metrics:
                for k, v in metrics.items():
                    mlflow.log_metric(k, float(v))
            for path in artifacts or []:
                mlflow.log_artifact(path, artifact_path)
            run_id = run.info.run_id
    return {"run_id": run_id, **provenance, "queue_dir": queue_dir}
