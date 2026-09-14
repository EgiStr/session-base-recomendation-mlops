# tests/streaming/test_transport.py
# Given fake producer/consumer / When send/consume_loop / Then processor receives decoded events
import json
from unittest.mock import MagicMock

from src.streaming.consumer import consume_loop
from src.streaming.producer import EventProducer


def test_producer_send_path():
    inner = MagicMock()
    EventProducer(inner, topic="t").send({"a": 1})
    inner.send.assert_called_once_with("t", json.dumps({"a": 1}).encode())


def test_producer_produce_path():
    class P:
        def __init__(self):
            self.calls = []

        def produce(self, topic, payload):
            self.calls.append((topic, payload))

    p = P()
    EventProducer(p, topic="t").send({"b": 2})
    assert p.calls == [("t", json.dumps({"b": 2}).encode())]


def test_consume_loop_poll_dict_batch():
    msg = MagicMock()
    msg.value = json.dumps({"session_id": "S"}).encode()

    class C:
        def __init__(self):
            self.calls = 0

        def poll(self, timeout):
            self.calls += 1
            return {"p": [msg]} if self.calls == 1 else None

    proc = MagicMock()
    consume_loop(C(), proc)
    proc.apply_event.assert_called_once_with({"session_id": "S"})


def test_consume_loop_iterable_consumer():
    msg = MagicMock()
    msg.value = {"already": "decoded"}
    proc = MagicMock()
    consume_loop([msg], proc)
    proc.apply_event.assert_called_once_with({"already": "decoded"})
