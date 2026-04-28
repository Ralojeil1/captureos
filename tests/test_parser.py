"""Tests for CaptureOS parser — item splitting, date/time extraction."""
from datetime import date
from captureos.parser import (
    split_items,
    detect_explicit_prefix,
    strip_prefix,
    extract_date_time,
    parse_capture_items,
)


class TestSplitItems:
    def test_single_item(self):
        result = split_items("Dentist tomorrow 3pm")
        assert len(result) == 1
        assert result[0] == "Dentist tomorrow 3pm"

    def test_empty(self):
        assert split_items("") == []
        assert split_items("   ") == []

    def test_period_separated(self):
        result = split_items("Call Alex Friday 10am. Remember to buy batteries Saturday.")
        assert len(result) == 2
        assert "Call Alex" in result[0]
        assert "buy batteries" in result[1]

    def test_and_separated(self):
        result = split_items("Call Alex Friday and remember to buy batteries Saturday")
        assert len(result) == 2

    def test_semicolon_separated(self):
        result = split_items("Dentist tomorrow 3pm; call Alex Friday 10am")
        assert len(result) == 2

    def test_newline_separated(self):
        result = split_items("Dentist tomorrow 3pm\nCall Alex Friday 10am")
        assert len(result) == 2

    def test_numbered_list(self):
        result = split_items("1. Dentist tomorrow 3pm\n2. Call Alex Friday 10am")
        assert len(result) == 2

    def test_process_this_prefix(self):
        result = split_items("Process this: met Jordan today. He wants the landing page by Thursday.")
        # Should split on periods
        assert len(result) >= 1
        assert "met Jordan" in result[0]


class TestExplicitPrefix:
    def test_task_prefix(self):
        assert detect_explicit_prefix("Task: follow up with Sarah") == "task_reminder"

    def test_reminder_prefix(self):
        assert detect_explicit_prefix("Reminder: submit invoice Friday") == "task_reminder"

    def test_meeting_prefix(self):
        assert detect_explicit_prefix("Meeting: discuss Q4 roadmap Monday 2pm") == "event_meeting"

    def test_event_prefix(self):
        assert detect_explicit_prefix("Event: company picnic Saturday") == "event_meeting"

    def test_idea_prefix(self):
        assert detect_explicit_prefix("Idea: build reusable onboarding agent") == "idea_note"

    def test_note_prefix(self):
        assert detect_explicit_prefix("Note: client wants faster turnaround") == "idea_note"

    def test_call_prefix(self):
        assert detect_explicit_prefix("Call: Alex Friday 10am") == "event_meeting"

    def test_no_prefix(self):
        assert detect_explicit_prefix("Dentist tomorrow 3pm") is None

    def test_case_insensitive(self):
        assert detect_explicit_prefix("TASK: do the thing") == "task_reminder"
        assert detect_explicit_prefix("IdEa: something cool") == "idea_note"

    def test_prefix_with_dash(self):
        assert detect_explicit_prefix("Task - follow up") == "task_reminder"
        assert detect_explicit_prefix("Meeting — discuss") == "event_meeting"


class TestStripPrefix:
    def test_removes_prefix(self):
        assert strip_prefix("Task: follow up with Sarah") == "follow up with Sarah"

    def test_preserves_no_prefix(self):
        assert strip_prefix("Dentist tomorrow 3pm") == "Dentist tomorrow 3pm"

    def test_removes_dash_prefix(self):
        assert strip_prefix("Idea - build something") == "build something"


class TestExtractDateTime:
    def test_iso_date(self):
        result = extract_date_time("Event on 2026-04-29")
        assert result["date"] == "2026-04-29"
        assert result["has_date"] is True

    def test_named_date(self):
        result = extract_date_time("Meeting April 28", reference_date=date(2026, 4, 20))
        assert result["date"] == "2026-04-28"

    def test_named_date_day_first(self):
        result = extract_date_time("Meeting 28 April 2026", reference_date=date(2026, 4, 20))
        assert result["date"] == "2026-04-28"

    def test_tomorrow(self):
        result = extract_date_time("Dentist tomorrow", reference_date=date(2026, 4, 28))
        assert result["date"] == "2026-04-29"
        assert result["has_date"] is True

    def test_today(self):
        result = extract_date_time("Meeting today", reference_date=date(2026, 4, 28))
        assert result["date"] == "2026-04-28"

    def test_day_of_week(self):
        # April 28, 2026 is a Tuesday. "Friday" should be May 1.
        result = extract_date_time("Call Friday", reference_date=date(2026, 4, 28))
        assert result["date"] == "2026-05-01"
        assert result["has_date"] is True

    def test_next_day_of_week(self):
        # April 28, 2026 is Tuesday. Next Monday should be May 4.
        result = extract_date_time("Call next Monday", reference_date=date(2026, 4, 28))
        assert result["date"] == "2026-05-04"

    def test_time_3pm(self):
        result = extract_date_time("Meeting at 3pm")
        assert result["time"] == "15:00"
        assert result["has_time"] is True

    def test_time_24h(self):
        result = extract_date_time("Meeting at 15:00")
        assert result["time"] == "15:00"
        assert result["has_time"] is True

    def test_time_9am(self):
        result = extract_date_time("Meeting at 9am")
        assert result["time"] == "09:00"

    def test_time_with_minutes(self):
        result = extract_date_time("Meeting at 3:30pm")
        assert result["time"] == "15:30"

    def test_time_12pm(self):
        result = extract_date_time("Lunch at 12pm")
        assert result["time"] == "12:00"

    def test_time_12am(self):
        result = extract_date_time("Call at 12am")
        assert result["time"] == "00:00"

    def test_all_day_when_date_only(self):
        result = extract_date_time("Task: submit report Friday", reference_date=date(2026, 4, 28))
        assert result["has_date"] is True
        assert result["has_time"] is False
        assert result["is_all_day"] is True

    def test_not_all_day_when_time_present(self):
        result = extract_date_time("Dentist tomorrow 3pm", reference_date=date(2026, 4, 28))
        assert result["is_all_day"] is False

    def test_no_date_no_time(self):
        result = extract_date_time("Idea: build something cool")
        assert result["date"] is None
        assert result["time"] is None
        assert result["has_date"] is False
        assert result["has_time"] is False

    def test_named_month_with_day(self):
        result = extract_date_time("Meeting March 15", reference_date=date(2026, 4, 28))
        assert result["date"] == "2026-03-15"

    def test_named_month_abbreviation(self):
        result = extract_date_time("Meeting Dec 25", reference_date=date(2026, 4, 28))
        assert result["date"] == "2026-12-25"


class TestParseCaptureItems:
    def test_single_item(self):
        result = parse_capture_items("Dentist tomorrow 3pm", reference_date=date(2026, 4, 28))
        assert len(result) == 1
        assert result[0]["date"] == "2026-04-29"
        assert result[0]["time"] == "15:00"
        assert result[0]["explicit_basket"] is None

    def test_multi_item(self):
        result = parse_capture_items(
            "Call Alex Friday 10am. Idea: build a dashboard.",
            reference_date=date(2026, 4, 28),
        )
        assert len(result) == 2
        assert result[1]["explicit_basket"] == "idea_note"
        assert result[1]["cleaned_text"] == "build a dashboard."

    def test_explicit_prefix(self):
        result = parse_capture_items("Task: follow up with Sarah Monday")
        assert result[0]["explicit_basket"] == "task_reminder"
        assert "follow up with Sarah" in result[0]["cleaned_text"]

    def test_empty_input(self):
        result = parse_capture_items("")
        assert result == []
