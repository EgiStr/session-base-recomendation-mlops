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
