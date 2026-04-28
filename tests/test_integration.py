"""End-to-end integration tests for CaptureOS.

These tests validate that the CLI classifier correctly routes
real-world natural-language inputs into the right baskets.
This is the most important test file — it validates classification accuracy.
"""

import os
import sys
import tempfile
import json
from datetime import date

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from captureos.classifier import Basket, CaptureItem
from captureos.parser import parse_capture_items
from captureos.router import RouterConfig, CaptureRouter, route_all
from captureos.writer import write_to_inbox, read_inbox
from captureos.conflict import ConflictDetector, CalendarEvent


# ── Test the heuristic classifier from cli.py ──
from captureos.cli import classify, _classify_item, _load_config


class TestClassifierHeuristics:
    """Test the deterministic classifier against real inputs."""

    def config(self):
        return RouterConfig()

    def classify_single(self, text, ref_date=None):
        """Classify a single input and return the first item."""
        result = classify(text, self.config())
        if not result.items:
            return None
        return result.items[0]

    # ── Event / Meeting classification ──

    def test_dentist_timed(self):
        item = self.classify_single("Dentist tomorrow 3pm")
        assert item is not None
        assert item.basket == Basket.EVENT_MEETING, f"Expected Event/Meeting, got {item.basket}"
        assert item.time == "15:00"

    def test_meeting_specific_time(self):
        item = self.classify_single("Meeting with Sarah Monday 10am about partnership")
        assert item.basket == Basket.EVENT_MEETING
        assert item.time == "10:00"

    def test_call_timed(self):
        item = self.classify_single("Call Alex Friday 10am about the launch")
        assert item.basket == Basket.EVENT_MEETING
        assert item.time == "10:00"

    def test_appointment(self):
        item = self.classify_single("Doctor appointment Tuesday 2pm")
        assert item.basket == Basket.EVENT_MEETING

    def test_lunch_event(self):
        item = self.classify_single("Lunch with team Friday 12pm")
        assert item.basket == Basket.EVENT_MEETING

    def test_dinner_large_event(self):
        item = self.classify_single("Dinner with team Friday 8pm")
        assert item.basket == Basket.EVENT_MEETING
        # Large event → 120 min
        assert item.duration_minutes == 120

    def test_sync_meeting(self):
        item = self.classify_single("Sync with engineering Monday 9am")
        assert item.basket == Basket.EVENT_MEETING

    def test_standup(self):
        item = self.classify_single("Standup Monday 9am")
        assert item.basket == Basket.EVENT_MEETING

    # ── Task / Reminder classification ──

    def test_follow_up_task(self):
        item = self.classify_single("Follow up with Omar Friday 11am")
        assert item.basket == Basket.TASK_REMINDER

    def test_submit_task(self):
        item = self.classify_single("Submit invoice Friday")
        assert item.basket == Basket.TASK_REMINDER
        assert item.is_all_day is True

    def test_remember_reminder(self):
        item = self.classify_single("Remember to renew passport next Monday")
        assert item.basket == Basket.TASK_REMINDER

    def test_finish_task(self):
        item = self.classify_single("Finish the quarterly report by Thursday")
        assert item.basket == Basket.TASK_REMINDER

    def test_explicit_task_prefix(self):
        item = self.classify_single("Task: follow up with Sarah")
        assert item.basket == Basket.TASK_REMINDER
        assert item.confidence == 1.0  # explicit prefix → high confidence

    def test_explicit_reminder_prefix(self):
        item = self.classify_single("Reminder: buy batteries Saturday")
        assert item.basket == Basket.TASK_REMINDER

    # ── Idea / Note classification ──

    def test_idea_keyword(self):
        item = self.classify_single("Idea: build reusable onboarding dashboard for clients")
        assert item.basket == Basket.IDEA_NOTE
        assert item.confidence == 1.0  # explicit prefix

    def test_note_keyword(self):
        item = self.classify_single("Note: client wants faster turnaround on designs")
        assert item.basket == Basket.IDEA_NOTE

    def test_think_keyword(self):
        item = self.classify_single("Think about building a habit tracker")
        assert item.basket == Basket.IDEA_NOTE

    def test_maybe_keyword(self):
        item = self.classify_single("Maybe we could use AI for the onboarding flow")
        assert item.basket == Basket.IDEA_NOTE

    def test_explore_keyword(self):
        item = self.classify_single("Explore using WebSockets for real-time updates")
        assert item.basket == Basket.IDEA_NOTE

    def test_ambiguous_defaults_to_idea(self):
        """Ambiguous input without clear signals should default to idea/note."""
        item = self.classify_single("Something about the project structure")
        assert item.basket == Basket.IDEA_NOTE

    # ── Multi-item classification ──

    def test_multi_item_mixed(self):
        result = classify(
            "Call Alex Friday 10am. Idea: build a dashboard. Follow up with Sarah Monday.",
            self.config(),
        )
        assert len(result.items) >= 2
        baskets = [item.basket for item in result.items]
        assert Basket.EVENT_MEETING in baskets
        assert Basket.IDEA_NOTE in baskets

    # ── Explicit prefix edge cases ──

    def test_case_insensitive_prefix(self):
        item = self.classify_single("TASK: do the thing")
        assert item.basket == Basket.TASK_REMINDER

    def test_meeting_prefix_calendar(self):
        item = self.classify_single("Meeting: discuss Q4 roadmap Monday 2pm")
        assert item.basket == Basket.EVENT_MEETING

    # ── Date/time edge cases ──

    def test_date_only_event_keyword(self):
        item = self.classify_single("Dentist Tuesday")
        assert item.basket == Basket.EVENT_MEETING
        assert item.is_all_day is True

    def test_no_date_idea(self):
        item = self.classify_single("Idea: simple meal planning template")
        assert item.basket == Basket.IDEA_NOTE
        assert item.date is None
        assert item.time is None

    def test_process_this(self):
        """Process this should split and classify multiple items."""
        result = classify(
            "Process this: met Jordan today. He wants the new landing page by Thursday. "
            "Also had an idea for a simple weekly client report generator.",
            self.config(),
        )
        assert len(result.items) >= 1


class TestRouter:
    def config(self):
        return RouterConfig(
            vault_path="/tmp/capture-test",
            calendar_enabled=False,
        )

    def test_routes_event_to_inbox_when_no_calendar(self):
        item = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="Dentist",
            date="2026-04-29",
            time="15:00",
            duration_minutes=60,
            confidence=0.95,
            reasoning="",
        )
        router = CaptureRouter(self.config())
        decision = router.route(item)
        assert decision.action == "save_inbox"
        assert "capture-events-meetings.md" in decision.destination

    def test_routes_idea_to_inbox(self):
        item = CaptureItem(
            basket=Basket.IDEA_NOTE,
            title="Build a dashboard",
            confidence=0.9,
            reasoning="",
        )
        router = CaptureRouter(self.config())
        decision = router.route(item)
        assert decision.action == "save_inbox"

    def test_routes_task_to_inbox(self):
        item = CaptureItem(
            basket=Basket.TASK_REMINDER,
            title="Follow up",
            date="2026-04-29",
            confidence=1.0,
            reasoning="",
        )
        router = CaptureRouter(self.config())
        decision = router.route(item)
        assert decision.action == "save_inbox"

    def test_conflict_triggers_approval(self):
        config = RouterConfig(
            vault_path="/tmp/capture-test",
            calendar_enabled=True,
            calendar_provider="google",
        )
        detector = ConflictDetector([
            CalendarEvent("Existing Meeting", "2026-04-29", "14:00", "16:00"),
        ])
        item = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="New Meeting",
            date="2026-04-29",
            time="15:00",
            duration_minutes=60,
            confidence=0.9,
            reasoning="",
        )
        router = CaptureRouter(config, detector)
        decision = router.route(item)
        assert decision.action == "ask_user"
        assert decision.requires_approval is True

    def test_duration_large_event(self):
        config = self.config()
        router = CaptureRouter(config)
        item = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="Dinner with team",
            date="2026-04-29",
            time="20:00",
            confidence=0.9,
            reasoning="",
        )
        assert router._event_duration(item) == 120  # large event

    def test_duration_meeting(self):
        config = self.config()
        router = CaptureRouter(config)
        item = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="Sync with engineering",
            confidence=0.9,
            reasoning="",
        )
        assert router._event_duration(item) == 60


class TestEndToEnd:
    """Full end-to-end: classify → route → write → read."""

    def test_full_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = RouterConfig(
                vault_path=tmp,
                wiki_dir="wiki",
            )

            # 1. Classify
            result = classify("Dentist tomorrow 3pm", config)
            assert len(result.items) == 1
            item = result.items[0]
            assert item.basket == Basket.EVENT_MEETING

            # 2. Route
            router = CaptureRouter(config)
            decision = router.route(item)
            assert decision.action == "save_inbox"

            # 3. Write
            filepath = os.path.join(tmp, "wiki", "capture-events-meetings.md")
            write_to_inbox(item, filepath)

            # 4. Read back
            items = read_inbox(filepath)
            assert len(items) >= 1
            assert any("Dentist" in i for i in items)

    def test_multi_item_full_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = RouterConfig(
                vault_path=tmp,
                wiki_dir="wiki",
            )

            result = classify(
                "Dentist tomorrow 3pm. Follow up with Sarah Friday. Idea: build a dashboard.",
                config,
            )
            assert len(result.items) >= 2

            # All should be classified
            baskets = {item.basket for item in result.items}
            assert len(baskets) >= 2  # at least two different baskets

    def test_conflict_end_to_end(self):
        """Test the full conflict detection pipeline."""
        detector = ConflictDetector([
            CalendarEvent("Existing", "2026-04-29", "14:00", "16:00"),
            CalendarEvent("Another", "2026-04-29", "09:00", "10:00"),
        ])

        config = RouterConfig(
            calendar_enabled=True,
            calendar_provider="google",
        )

        router = CaptureRouter(config, detector)

        # Clear slot: 11:00
        item = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="Team sync",
            date="2026-04-29",
            time="11:00",
            duration_minutes=60,
            confidence=0.9,
            reasoning="",
        )
        decision = router.route(item)
        assert decision.action != "ask_user", f"Should not need approval: {decision.approval_reason}"

        # Conflicting slot: 15:00
        item = CaptureItem(
            basket=Basket.EVENT_MEETING,
            title="Another meeting",
            date="2026-04-29",
            time="15:00",
            duration_minutes=60,
            confidence=0.9,
            reasoning="",
        )
        decision = router.route(item)
        assert decision.action == "ask_user"
        assert decision.conflict is not None
        assert decision.conflict.has_conflict

    def test_free_slots(self):
        detector = ConflictDetector([
            CalendarEvent("Morning meeting", "2026-04-29", "09:00", "10:30"),
            CalendarEvent("Lunch", "2026-04-29", "12:00", "13:00"),
            CalendarEvent("Afternoon call", "2026-04-29", "15:00", "16:00"),
        ])

        slots = detector.find_free_slots("2026-04-29", 60)
        # Should find slots between events
        assert len(slots) >= 2  # 10:30-12:00 and 13:00-15:00


class TestConfigLoading:
    """Test that config can be loaded gracefully."""

    def test_default_config(self):
        config = RouterConfig()
        assert config.duration_meeting_call == 60
        assert config.calendar_enabled is False
        assert config.calendar_provider == "none"
        assert config.timezone == "UTC"

    def test_custom_config(self):
        config = RouterConfig(
            calendar_enabled=True,
            calendar_provider="google",
            timezone="Asia/Dubai",
            duration_large_event=180,
        )
        assert config.calendar_enabled is True
        assert config.timezone == "Asia/Dubai"
        assert config.duration_large_event == 180
