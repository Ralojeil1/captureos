"""Tests for CaptureOS classifier — structured output and accuracy."""
import json
import pytest
from captureos.classifier import (
    Basket, CaptureItem, CaptureResult,
    CLASSIFY_FUNCTION_SCHEMA,
)


class TestBasketEnum:
    def test_basket_values(self):
        assert Basket.TASK_REMINDER.value == "task_reminder"
        assert Basket.EVENT_MEETING.value == "event_meeting"
        assert Basket.IDEA_NOTE.value == "idea_note"

    def test_basket_labels(self):
        item = CaptureItem(basket=Basket.EVENT_MEETING, title="test", confidence=1.0, reasoning="")
        assert item.basket_label == "Event / Meeting"

        item.basket = Basket.TASK_REMINDER
        assert item.basket_label == "Task / Reminder"

        item.basket = Basket.IDEA_NOTE
        assert item.basket_label == "Idea / Note"


class TestCaptureItem:
    def test_to_dict(self):
        item = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="Dentist appointment",
            date="2026-04-29",
            time="15:00",
            duration_minutes=60,
            is_all_day=False,
            confidence=0.95,
            reasoning="Clear appointment with time",
        )
        d = item.to_dict()
        assert d["basket"] == "event_meeting"
        assert d["title"] == "Dentist appointment"
        assert d["date"] == "2026-04-29"
        assert d["time"] == "15:00"
        assert d["duration_minutes"] == 60
        assert d["is_all_day"] is False
        assert d["confidence"] == 0.95

    def test_to_json(self):
        item = CaptureItem(
            basket=Basket.TASK_REMINDER,
            title="Follow up",
            confidence=0.8,
            reasoning="Task keyword",
        )
        j = item.to_json()
        data = json.loads(j)
        assert data["basket"] == "task_reminder"
        assert data["title"] == "Follow up"

    def test_is_timed(self):
        timed = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="Meeting",
            date="2026-04-29",
            time="15:00",
            confidence=1.0,
            reasoning="",
        )
        assert timed.is_timed is True

        all_day = CaptureItem(
            basket=Basket.TASK_REMINDER,
            title="Submit report",
            date="2026-04-29",
            is_all_day=True,
            confidence=1.0,
            reasoning="",
        )
        assert all_day.is_timed is False

    def test_default_values(self):
        item = CaptureItem(
            basket=Basket.IDEA_NOTE,
            title="An idea",
            confidence=0.5,
            reasoning="default",
        )
        assert item.date is None
        assert item.time is None
        assert item.duration_minutes == 60  # default
        assert item.is_all_day is False


class TestCaptureResult:
    def test_single_item(self):
        item = CaptureItem(
            basket=Basket.IDEA_NOTE,
            title="Build a dashboard",
            confidence=0.9,
            reasoning="idea keyword",
        )
        result = CaptureResult(items=[item], raw_input="Idea: Build a dashboard")
        assert len(result.items) == 1
        assert result.items[0].title == "Build a dashboard"

    def test_summary(self):
        item = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="Dentist",
            date="2026-04-29",
            time="15:00",
            duration_minutes=60,
            confidence=0.95,
            reasoning="",
        )
        result = CaptureResult(items=[item])
        summary = result.summary()
        assert "Event / Meeting" in summary
        assert "Dentist" in summary
        assert "2026-04-29" in summary
        assert "15:00" in summary

    def test_multiple_items_summary(self):
        items = [
            CaptureItem(basket=Basket.EVENT_MEETING, title="Meeting", date="2026-05-01", time="10:00",
                       duration_minutes=60, confidence=0.9, reasoning=""),
            CaptureItem(basket=Basket.IDEA_NOTE, title="New feature idea", confidence=0.8, reasoning=""),
        ]
        result = CaptureResult(items=items)
        summary = result.summary()
        assert "Meeting" in summary
        assert "New feature idea" in summary

    def test_to_dict_and_json(self):
        items = [
            CaptureItem(basket=Basket.TASK_REMINDER, title="Task 1", confidence=1.0, reasoning=""),
            CaptureItem(basket=Basket.IDEA_NOTE, title="Idea 1", confidence=1.0, reasoning=""),
        ]
        result = CaptureResult(items=items, raw_input="Multiple items")
        d = result.to_dict()
        assert len(d["items"]) == 2
        assert d["raw_input"] == "Multiple items"

        j = result.to_json()
        assert "Task 1" in j
        assert "Idea 1" in j


class TestFunctionSchema:
    def test_schema_valid_json(self):
        """Schema must be valid JSON-serializable."""
        s = json.dumps(CLASSIFY_FUNCTION_SCHEMA)
        parsed = json.loads(s)
        assert parsed["name"] == "classify_capture"

    def test_schema_has_required_fields(self):
        props = CLASSIFY_FUNCTION_SCHEMA["parameters"]["properties"]["items"]["items"]["properties"]
        assert "basket" in props
        assert "title" in props
        assert "date" in props
        assert "time" in props
        assert "duration_minutes" in props
        assert "is_all_day" in props
        assert "confidence" in props
        assert "reasoning" in props

    def test_basket_enum_values(self):
        enum_vals = CLASSIFY_FUNCTION_SCHEMA["parameters"]["properties"]["items"]["items"]["properties"]["basket"]["enum"]
        assert "task_reminder" in enum_vals
        assert "event_meeting" in enum_vals
        assert "idea_note" in enum_vals
        assert len(enum_vals) == 3  # exactly three baskets
