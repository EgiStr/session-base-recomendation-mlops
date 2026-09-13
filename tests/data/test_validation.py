# tests/data/test_validation.py
# Given batch with invalid timestamps + duplicate event_ids
# When validation runs / Then quarantined with per-check counts
import time

from src.data.schemas import CanonicalEvent, EventContext
from src.data.validation import validate_batch


def _ev(eid, ts):
    return CanonicalEvent(event_id=eid, session_id="trivago:S1",
        timestamp=ts, item_id="H1", event_type="click",
        context=EventContext())


def test_corrupt_batch_quarantined_with_counts():
    # Given
    now = int(time.time())
    batch = [_ev("e1", now), _ev("e1", now), _ev("e2", "not-epoch")]
    # When
    report = validate_batch(batch)
    # Then
    assert report["quarantined"] == 2
    assert report["per_check"]["duplicate"] >= 1
    assert report["per_check"]["timestamp"] >= 1
    assert len(report["clean"]) == 1


def test_late_arrival_quarantined():
    # Given event older than 7 days / When validated / Then late-arrival quarantine
    old = int(time.time()) - 8 * 86400
    report = validate_batch([_ev("e9", old)])
    # Then
    assert report["quarantined"] == 1
    assert report["per_check"]["late_arrival"] == 1
