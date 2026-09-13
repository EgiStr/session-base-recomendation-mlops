"""Kafka event producer (thin wrapper; real broker only in compose)."""
from __future__ import annotations

import json
from typing import Any, Dict


class EventProducer:
    def __init__(self, producer: Any, topic: str = "triprank-events"):
        self.producer = producer
        self.topic = topic

    def send(self, event: Dict[str, Any]) -> None:
        payload = json.dumps(event, default=str).encode()
        if hasattr(self.producer, "send"):
            self.producer.send(self.topic, payload)
        elif hasattr(self.producer, "produce"):
            self.producer.produce(self.topic, payload)
        else:  # pragma: no cover - duck-type fallback
            raise TypeError("producer must expose send() or produce()")
