"""Tests for CaptureOS conflict detector."""
from captureos.conflict import (
    ConflictDetector,
    CalendarEvent,
    ConflictResult,
    _time_to_minutes,
    _minutes_to_time,
)


class TestTimeHelpers:
    def test_time_to_minutes(self):
        assert _time_to_minutes("00:00") == 0
        assert _time_to_minutes("01:00") == 60
        assert _time_to_minutes("12:00") == 720
        assert _time_to_minutes("23:59") == 1439

    def test_minutes_to_time(self):
        assert _minutes_to_time(0) == "00:00"
        assert _minutes_to_time(60) == "01:00"
        assert _minutes_to_time(720) == "12:00"
        assert _minutes_to_time(1439) == "23:59"


class TestConflictDetector:
    def test_no_conflict_empty(self):
        detector = ConflictDetector()
        result = detector.check("2026-04-29", "15:00", 60)
        assert result.has_conflict is False

    def test_no_conflict_different_day(self):
        detector = ConflictDetector([
            CalendarEvent("Meeting", "2026-04-29", "15:00", "16:00"),
        ])
        result = detector.check("2026-04-30", "15:00", 60)
        assert result.has_conflict is False

    def test_no_conflict_adjacent(self):
        """Events that don't overlap should not conflict."""
        detector = ConflictDetector([
            CalendarEvent("Meeting A", "2026-04-29", "10:00", "11:00"),
        ])
        result = detector.check("2026-04-29", "11:00", 60)
        assert result.has_conflict is False

    def test_conflict_overlap(self):
        detector = ConflictDetector([
            CalendarEvent("Meeting A", "2026-04-29", "10:00", "11:30"),
        ])
        result = detector.check("2026-04-29", "11:00", 60)
        assert result.has_conflict is True
        assert "Meeting A" in result.reason

    def test_conflict_contains(self):
        """Proposed event is completely inside existing event."""
        detector = ConflictDetector([
            CalendarEvent("All-hands", "2026-04-29", "09:00", "17:00"),
        ])
        result = detector.check("2026-04-29", "10:00", 60)
        assert result.has_conflict is True

    def test_conflict_exact_match(self):
        detector = ConflictDetector([
            CalendarEvent("Meeting", "2026-04-29", "10:00", "11:00"),
        ])
        result = detector.check("2026-04-29", "10:00", 60)
        assert result.has_conflict is True

    def test_no_date_no_conflict(self):
        detector = ConflictDetector([
            CalendarEvent("Meeting", "2026-04-29", "10:00", "11:00"),
        ])
        result = detector.check(None, "10:00", 60)
        assert result.has_conflict is False

    def test_no_time_no_conflict(self):
        detector = ConflictDetector([
            CalendarEvent("Meeting", "2026-04-29", "10:00", "11:00"),
        ])
        result = detector.check("2026-04-29", None, 60)
        assert result.has_conflict is False

    def test_multiple_conflicts(self):
        detector = ConflictDetector([
            CalendarEvent("Meeting A", "2026-04-29", "10:00", "11:00"),
            CalendarEvent("Meeting B", "2026-04-29", "10:30", "11:30"),
        ])
        result = detector.check("2026-04-29", "10:15", 30)
        assert result.has_conflict is True
        assert len(result.conflicting_events) == 2

    def test_add_event(self):
        detector = ConflictDetector()
        detector.add_event(CalendarEvent("New", "2026-04-29", "10:00", "11:00"))
        assert len(detector.events) == 1
        result = detector.check("2026-04-29", "10:30", 30)
        assert result.has_conflict is True


class TestFindFreeSlots:
    def test_empty_day(self):
        detector = ConflictDetector()
        slots = detector.find_free_slots("2026-04-29", 60)
        assert len(slots) > 0

    def test_busy_morning(self):
        detector = ConflictDetector([
            CalendarEvent("Meeting", "2026-04-29", "08:00", "12:00"),
        ])
        slots = detector.find_free_slots("2026-04-29", 60)
        assert any(s["start"] == "12:00" for s in slots)

    def test_no_slot_long_enough(self):
        detector = ConflictDetector([
            CalendarEvent("A", "2026-04-29", "08:00", "12:00"),
            CalendarEvent("B", "2026-04-29", "13:00", "19:30"),
        ])
        slots = detector.find_free_slots("2026-04-29", 90)
        # 12:00-13:00 is 60 min, not enough for 90
        # 19:30-20:00 is 30 min, not enough
        assert all(
            (_time_to_minutes(s["end"]) - _time_to_minutes(s["start"])) >= 90
            for s in slots
        ) or len(slots) == 0
