"""Native MLflow Registry wrapper: HotelRanker + Champion/Challenger aliases."""
from __future__ import annotations

import json
import os
import time
from typing import Any


class ModelRegistry:
    def __init__(self, client: Any, queue_dir: str = "/tmp/triprank-queue"):
        self.client = client
        self.queue_dir = queue_dir

    def register_model(self, name: str, run_id: str,
                       source: str | None = None, alias: str = "Challenger") -> dict:
        try:
            self.client.create_registered_model(name)
        except Exception:  # already exists → proceed to version
            pass
        mv = self.client.create_model_version(name, source or f"runs:/{run_id}/model", run_id)
        version = str(mv.version)
        self.client.set_registered_model_alias(name, alias, version)
        return {"name": name, "version": version, "run_id": run_id, "alias": alias}

    def promote(self, name: str, version: str) -> dict:
        self.client.set_registered_model_alias(name, "Champion", str(version))
        return {"name": name, "version": str(version), "alias": "Champion"}


def promote(champion: str, challenger: str, registry_ok: bool, queue_dir: str) -> dict:
    """Outage path: queue locally + BLOCK promotion (pure function for testability)."""
    if not registry_ok:
        os.makedirs(queue_dir, exist_ok=True)
        path = os.path.join(queue_dir, f"promote-{challenger}-{int(time.time())}.json")
        with open(path, "w") as f:
            json.dump({"champion": champion, "challenger": challenger}, f)
        return {"status": "BLOCKED", "queued": True, "queue_path": path}
    return {"status": "READY", "queued": False}
