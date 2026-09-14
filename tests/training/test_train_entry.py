# tests/training/test_train_entry.py
# Given fake client / When run_training / Then params+metrics+artifacts logged
from unittest.mock import MagicMock

from src.training.train import _git_commit, run_training


def test_run_training_with_fake_client(tmp_path):
    client = MagicMock()
    art = tmp_path / "m.txt"
    art.write_text("x")
    out = run_training("ds@v1", client=client, params={"a": 1},
                       metrics={"m": 0.5}, artifacts=[str(art)])
    assert out["dataset_version"] == "ds@v1" and out["run_id"]
    client.log_param.assert_called()
    client.log_metric.assert_called_once_with("m", 0.5)
    client.log_artifact.assert_called_once_with(str(art), None)


def test_git_commit_returns_tuple():
    commit, dirty = _git_commit()
    assert isinstance(commit, str) and isinstance(dirty, bool)
