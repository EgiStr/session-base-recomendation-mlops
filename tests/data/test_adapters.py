# tests/data/test_adapters.py
# Given OTTO {session s9, order a42, no city/device/filters}
# When adapter normalizes / Then context nulls valid under key otto:s9
from src.data.adapters.otto import normalize_otto
from src.data.adapters.trivago import normalize_trivago
from src.data.schemas import namespaced_key


def test_otto_null_context_mapping():
    # Given
    raw = {"session_id": "s9", "order_id": "a42", "item_id": "a42",
           "timestamp": 1757760000, "event_type": "order"}
    # When
    ev = normalize_otto(raw)
    # Then
    assert ev.session_id == "otto:s9"
    assert ev.context.city is None and ev.context.device is None
    assert ev.context.filters is None


def test_namespace_isolation():
    # Given colliding raw ids / When namespaced / Then keys differ
    assert namespaced_key("trivago", "S1") != namespaced_key("otto", "S1")
    assert namespaced_key("trivago", "S1") == "trivago:S1"


def test_trivago_adapter_happy_path():
    # Given trivago click / When normalized / Then canonical fields kept
    raw = {"session_id": "S1", "item_id": "H10", "timestamp": 1757760000,
           "event_type": "click", "city": "Bali", "device": "mobile"}
    ev = normalize_trivago(raw)
    assert ev.session_id == "trivago:S1"
    assert ev.context.city == "Bali"
