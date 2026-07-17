"""Unit tests for timeline map-reduce deduplication."""
import pytest

from app.schemas.case import TimelineEvent
from app.services.ai.timeline_service import _dedupe, _is_duplicate


def ev(date: str, event: str) -> TimelineEvent:
    return TimelineEvent(date=date, event=event, description=None)


# ---------------------------------------------------------------------------
# _is_duplicate
# ---------------------------------------------------------------------------

def test_same_date_same_event_is_duplicate():
    a = ev("1973-04-24", "Kesavananda Bharati judgment delivered")
    b = ev("1973-04-24", "Kesavananda Bharati judgment delivered by Supreme Court")
    assert _is_duplicate(a, b)


def test_different_date_not_duplicate():
    a = ev("1973-04-24", "Judgment delivered")
    b = ev("1974-01-01", "Judgment delivered")
    assert not _is_duplicate(a, b)


def test_same_date_different_event_not_duplicate():
    a = ev("1973-04-24", "Judgment on basic structure")
    b = ev("1973-04-24", "Petition for habeas corpus filed")
    assert not _is_duplicate(a, b)


# ---------------------------------------------------------------------------
# _dedupe
# ---------------------------------------------------------------------------

def test_dedupe_removes_duplicates():
    events = [
        ev("1973-04-24", "Judgment delivered"),
        ev("1973-04-24", "Judgment delivered by Supreme Court bench"),  # near-dup
        ev("1978-01-25", "Maneka Gandhi passport impounded"),
    ]
    result = _dedupe(events)
    assert len(result) == 2


def test_dedupe_keeps_unique_events():
    events = [
        ev("1973-04-24", "Judgment on basic structure"),
        ev("1975-06-25", "Emergency declared"),
        ev("1977-03-20", "Emergency lifted"),
    ]
    result = _dedupe(events)
    assert len(result) == 3


def test_dedupe_empty():
    assert _dedupe([]) == []


def test_dedupe_single():
    events = [ev("2020-01-01", "Only event")]
    assert _dedupe(events) == events
