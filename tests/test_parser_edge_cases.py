"""Edge case tests for parser robustness — 20+ edge cases."""
from datetime import date
from captureos.parser import (
    split_items,
    extract_date_time,
    parse_capture_items,
)

REF = date(2026, 4, 28)  # Tuesday


class TestEdgeCasesExtractDateTime:
    """Test extract_date_time with 20+ edge cases."""

    def test_noon(self):
        """Call at noon — informal time."""
        result = extract_date_time("Call at noon", reference_date=REF)
        # Should parse "noon" as 12:00
        assert result["time"] == "12:00", f"Expected 12:00, got {result['time']}"
        assert result["has_time"] is True

    def test_midnight(self):
        """Call at midnight — informal time."""
        result = extract_date_time("Call at midnight", reference_date=REF)
        assert result["time"] == "00:00", f"Expected 00:00, got {result['time']}"
        assert result["has_time"] is True

    def test_time_range(self):
        """Meeting 3:00pm-4:00pm — time range."""
        result = extract_date_time("Meeting 3:00pm-4:00pm", reference_date=REF)
        # Should at least extract the start time
        assert result["time"] == "15:00", f"Expected 15:00, got {result['time']}"
        assert result["has_time"] is True

    def test_ordinal_january_1st(self):
        """January 1st — ordinal date."""
        result = extract_date_time("January 1st", reference_date=REF)
        assert result["date"] == "2026-01-01", f"Expected 2026-01-01, got {result['date']}"
        assert result["has_date"] is True

    def test_tomorrow_at_bare_hour(self):
        """Tomorrow at 8 — relative + bare hour."""
        result = extract_date_time("Tomorrow at 8", reference_date=REF)
        assert result["date"] == "2026-04-29", f"Expected 2026-04-29, got {result['date']}"
        # Bare hour "8" should be 08:00 or handle it as a raw number
        assert result["has_date"] is True

    def test_next_tuesday(self):
        """Next Tuesday — day calculation."""
        result = extract_date_time("Next Tuesday", reference_date=REF)
        # REF=Tuesday Apr 28. "Next Tuesday" should be May 5 (next week's Tuesday)
        assert result["date"] == "2026-05-05", f"Expected 2026-05-05, got {result['date']}"
        assert result["has_date"] is True

    def test_in_2_days(self):
        """In 2 days — relative with offset."""
        result = extract_date_time("In 2 days", reference_date=REF)
        # Should be April 30
        assert result["date"] == "2026-04-30", f"Expected 2026-04-30, got {result['date']}"
        assert result["has_date"] is True

    def test_this_friday(self):
        """This Friday — 'this' disambiguation."""
        result = extract_date_time("This Friday", reference_date=REF)
        # REF=Tuesday Apr 28. Friday = May 1
        assert result["date"] == "2026-05-01", f"Expected 2026-05-01, got {result['date']}"
        assert result["has_date"] is True

    def test_march_3rd_2026(self):
        """March 3rd, 2026 — ordinal + year."""
        result = extract_date_time("March 3rd, 2026", reference_date=REF)
        assert result["date"] == "2026-03-03", f"Expected 2026-03-03, got {result['date']}"
        assert result["has_date"] is True

    def test_numeric_slash_date(self):
        """3/15 — numeric slash date."""
        result = extract_date_time("Event on 3/15", reference_date=REF)
        assert result["date"] == "2026-03-15", f"Expected 2026-03-15, got {result['date']}"
        assert result["has_date"] is True

    def test_numeric_slash_date_with_year(self):
        """3/15/2026 — numeric slash date with year."""
        result = extract_date_time("Event on 3/15/2026", reference_date=REF)
        assert result["date"] == "2026-03-15", f"Expected 2026-03-15, got {result['date']}"
        assert result["has_date"] is True

    def test_24h_time(self):
        """Call at 14:30 — 24h time."""
        result = extract_date_time("Call at 14:30", reference_date=REF)
        assert result["time"] == "14:30", f"Expected 14:30, got {result['time']}"
        assert result["has_time"] is True

    def test_abbreviated_day_with_time(self):
        """Mon 10am — abbreviated day + time."""
        result = extract_date_time("Mon 10am", reference_date=REF)
        # REF=Tuesday Apr 28. Mon => upcoming Monday = May 4
        assert result["date"] == "2026-05-04", f"Expected 2026-05-04, got {result['date']}"
        assert result["time"] == "10:00", f"Expected 10:00, got {result['time']}"
        assert result["has_date"] is True
        assert result["has_time"] is True

    def test_late_night_11pm(self):
        """11pm — late night."""
        result = extract_date_time("Party at 11pm", reference_date=REF)
        assert result["time"] == "23:00", f"Expected 23:00, got {result['time']}"
        assert result["has_time"] is True

    def test_time_before_date(self):
        """8am tomorrow — time before date."""
        result = extract_date_time("8am tomorrow", reference_date=REF)
        assert result["date"] == "2026-04-29", f"Expected 2026-04-29, got {result['date']}"
        assert result["time"] == "08:00", f"Expected 08:00, got {result['time']}"
        assert result["has_date"] is True
        assert result["has_time"] is True

    def test_empty_input(self):
        """Empty input — should not crash."""
        result = extract_date_time("", reference_date=REF)
        assert result["date"] is None
        assert result["time"] is None
        assert result["has_date"] is False
        assert result["has_time"] is False

    def test_whitespace_only(self):
        """Whitespace-only input — should not crash."""
        result = extract_date_time("   \t\n  ", reference_date=REF)
        assert result["date"] is None
        assert result["time"] is None
        assert result["has_date"] is False

    def test_very_long_input(self):
        """Very long input — should not crash."""
        long_text = "Meeting " + "and then another meeting " * 500 + "tomorrow"
        result = extract_date_time(long_text, reference_date=REF)
        # Should handle long input without crash and still find tomorrow
        assert result["date"] == "2026-04-29", f"Expected 2026-04-29, got {result['date']}"

    def test_unicode_no_crash(self):
        """Café meeting mañana — should not crash."""
        result = extract_date_time("Café meeting mañana", reference_date=REF)
        assert result["date"] is None  # "mañana" not in English dictionary
        assert result["time"] is None
        # Just shouldn't crash

    def test_time_range_with_space_no_am_pm(self):
        """3:00 - 4:00pm — time range with spaces."""
        result = extract_date_time("Meeting 3:00 - 4:00pm", reference_date=REF)
        # The first time "3:00" has no am/pm, so it parses as 3am (03:00).
        # This is an inherent ambiguity — the pm on the second time doesn't disambiguate the first.
        assert result["time"] == "03:00", f"Expected 03:00 (ambiguous), got {result['time']}"
        assert result["has_time"] is True

    def test_in_5_days(self):
        """In 5 days — test another offset."""
        result = extract_date_time("In 5 days from now", reference_date=REF)
        # REF=Apr 28. 5 days later = May 3
        assert result["date"] == "2026-05-03", f"Expected 2026-05-03, got {result['date']}"

    def test_dot_time_no_am_pm(self):
        """Meeting at 3.30pm — dot separator in time."""
        # The TIME_RE won't match "3.30pm" but let's just check it doesn't crash
        result = extract_date_time("Meeting at 3.30pm", reference_date=REF)
        # Not required to parse this, just shouldn't crash
        assert result is not None

    def test_three_letter_month(self):
        """Jan 5 — three-letter month abbreviation."""
        result = extract_date_time("Jan 5", reference_date=REF)
        assert result["date"] == "2026-01-05", f"Expected 2026-01-05, got {result['date']}"

    def test_day_month_no_year(self):
        """5 Jan — day first, no year."""
        result = extract_date_time("5 Jan", reference_date=REF)
        assert result["date"] == "2026-01-05", f"Expected 2026-01-05, got {result['date']}"


class TestEdgeCasesSplitItems:
    """Test split_items with edge cases."""

    def test_empty_input(self):
        assert split_items("") == []

    def test_whitespace_only(self):
        assert split_items("   \t\n  ") == []

    def test_very_long_input(self):
        long_text = "Call Alex. " + "Remember to buy batteries. " * 500
        result = split_items(long_text)
        assert len(result) > 0
        assert "Call Alex" in result[0]

    def test_unicode(self):
        result = split_items("Café meeting. Mañana task.")
        assert len(result) >= 1
        assert "Café" in result[0]


class TestEdgeCasesParseCaptureItems:
    """Integration edge cases."""

    def test_noon_parsed(self):
        result = parse_capture_items("Call at noon", reference_date=REF)
        assert len(result) == 1
        assert result[0]["time"] == "12:00"

    def test_bare_hour_tomorrow(self):
        result = parse_capture_items("Meeting tomorrow at 8", reference_date=REF)
        assert len(result) == 1
        assert result[0]["date"] == "2026-04-29"

    def test_numeric_slash(self):
        result = parse_capture_items("Dentist 4/15", reference_date=REF)
        assert len(result) == 1
        assert result[0]["date"] == "2026-04-15"
