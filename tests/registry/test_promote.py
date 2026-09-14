# tests/registry/test_promote.py
# Given registry down / When promote / Then BLOCKED + queued file; else READY
from unittest.mock import MagicMock

from src.registry.registry import promote


def test_promote_blocked_queues(tmp_path):
    out = promote("v1", "v2", registry_ok=False, queue_dir=str(tmp_path))
    assert out["status"] == "BLOCKED" and out["queued"] is True
    assert (tmp_path / out["queue_path"].split("\\")[-1].split("/")[-1]).exists()


def test_promote_ready_no_queue():
    out = promote("v1", "v2", registry_ok=True, queue_dir="unused")
    assert out == {"status": "READY", "queued": False}


def test_register_model_alias_flow():
    from src.registry.registry import ModelRegistry

    client = MagicMock()
    client.create_model_version.return_value.version = "3"
    out = ModelRegistry(client).register_model("M", run_id="r1", alias="Champion")
    assert out == {"name": "M", "version": "3", "run_id": "r1", "alias": "Champion"}
