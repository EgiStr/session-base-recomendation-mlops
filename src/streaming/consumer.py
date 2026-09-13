"""Kafka consumer loop → SessionProcessor (real broker only in compose)."""
from __future__ import annotations

import json
from typing import Any, Callable


def consume_loop(consumer: Any, processor: Any,
                 decode: Callable[[bytes], Any] | None = None) -> None:
    decode = decode or (lambda b: json.loads(b.decode()))
    while True:
        batch = consumer.poll(1.0) if hasattr(consumer, "poll") else None
        if not batch:
            if hasattr(consumer, "__iter__"):
                for msg in consumer:
                    value = msg.value if hasattr(msg, "value") else msg
                    if isinstance(value, (bytes, bytearray)):
                        value = decode(bytes(value))
                    processor.apply_event(value)
                break
            break
        msgs = batch.values() if isinstance(batch, dict) else batch
        for m in msgs:
            value = m.value if hasattr(m, "value") else m
            if isinstance(value, (bytes, bytearray)):
                value = decode(bytes(value))
            processor.apply_event(value)
