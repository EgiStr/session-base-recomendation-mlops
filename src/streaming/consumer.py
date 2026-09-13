"""Kafka consumer loop → SessionProcessor (real broker only in compose)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

log = logging.getLogger("triprank.streaming")

TOPIC = "triprank-events"


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


def _build_consumer() -> Any:
    from kafka import KafkaConsumer

    # In-compose: kafka:29092 (INTERNAL listener). Host-side dev:
    # localhost:9092 (EXTERNAL listener). The broker advertises a reachable
    # address per listener — kafka-python follows metadata, so the bootstrap
    # host must match the side you run on.
    servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=servers,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="triprank-sessions",
        value_deserializer=lambda b: json.loads(b.decode()),
    )
    log.info("subscribed to %s @ %s", TOPIC, servers)
    return consumer


def _build_processor() -> Any:
    import redis as _redis

    from src.streaming.session_processor import SessionProcessor

    url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    client = _redis.Redis.from_url(url, decode_responses=True)
    log.info("streaming redis @ %s", url)
    return SessionProcessor(redis_client=client)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = _build_consumer()
    processor = _build_processor()
    log.info("streaming consumer online")
    consume_loop(consumer, processor)


if __name__ == "__main__":
    main()
