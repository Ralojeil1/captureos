"""CaptureOS Router — routes classified items to destinations.

Handles the decision logic:
- Does this go to a calendar? A markdown file? Both?
- What default duration applies?
- Should we ask the user first?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Callable

from captureos.classifier import Basket, CaptureItem
from captureos.conflict import ConflictDetector, ConflictResult


@dataclass
class RouterConfig:
    """Configuration for the capture router."""
    # Calendar settings
    calendar_enabled: bool = False
    calendar_provider: str = "none"  # "google", "apple", "caldav", "none"

    # Vault settings
    vault_path: Optional[str] = None   # e.g., ~/Documents/CaptureVault
    wiki_dir: str = "wiki"

    # Default durations (minutes)
    duration_meeting_call: int = 60
    duration_event_appointment: int = 60
    duration_large_event: int = 120
    duration_timed_task: int = 60

    # Reminders (minutes before event)
    default_reminders: list[int] = field(default_factory=lambda: [1440, 60])

    # Timezone
    timezone: str = "UTC"

    # Basket filenames
    basket_files: dict = field(default_factory=lambda: {
        Basket.TASK_REMINDER: "capture-tasks-reminders.md",
        Basket.EVENT_MEETING: "capture-events-meetings.md",
        Basket.IDEA_NOTE: "capture-ideas-notes.md",
    })

    # User name (optional, for display)
    user_name: str = ""


@dataclass
class RoutingDecision:
    """The outcome of deciding where a capture item should go."""
    item: CaptureItem
    action: str  # "create_event", "save_inbox", "ask_user", "both", "skip"
    destination: str = ""   # file path, calendar name, or reason
    duration_minutes: int = 60
    requires_approval: bool = False
    approval_reason: str = ""
    conflict: Optional[ConflictResult] = None


class CaptureRouter:
    """Routes classified capture items to their destinations.

    The router decides:
    - Whether to create a calendar event or save to a markdown inbox
    - What default duration to apply
    - Whether user approval is needed
    """

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        conflict_detector: Optional[ConflictDetector] = None,
    ):
        self.config = config or RouterConfig()
        self.conflict_detector = conflict_detector

    def route(self, item: CaptureItem) -> RoutingDecision:
        """Make a routing decision for a single capture item."""
        basket = item.basket

        if basket == Basket.EVENT_MEETING:
            return self._route_event(item)
        elif basket == Basket.TASK_REMINDER:
            return self._route_task(item)
        else:
            return self._route_idea(item)

    def _route_event(self, item: CaptureItem) -> RoutingDecision:
        """Route an event/meeting item."""
        # Determine duration
        duration = self._event_duration(item)

        # Check for conflicts if calendar is enabled
        conflict = None
        if self.config.calendar_enabled and self.conflict_detector:
            conflict = self.conflict_detector.check(item.date, item.time, duration)

        if conflict and conflict.has_conflict:
            return RoutingDecision(
                item=item,
                action="ask_user",
                destination=f"Calendar conflict: {conflict.reason}",
                duration_minutes=duration,
                requires_approval=True,
                approval_reason=conflict.reason,
                conflict=conflict,
            )

        if self.config.calendar_enabled and item.date:
            return RoutingDecision(
                item=item,
                action="create_event",
                destination=self.config.calendar_provider,
                duration_minutes=duration,
                requires_approval=False,
            )
        else:
            # Save to markdown inbox
            return RoutingDecision(
                item=item,
                action="save_inbox",
                destination=self._inbox_path(item.basket),
                duration_minutes=duration,
                requires_approval=False,
            )

    def _route_task(self, item: CaptureItem) -> RoutingDecision:
        """Route a task/reminder item."""
        duration = self.config.duration_timed_task if item.is_timed else 0

        # Tasks with clear dates go to calendar if enabled
        if self.config.calendar_enabled and item.date:
            # Undated tasks default to tomorrow all-day
            if not item.is_timed:
                item.is_all_day = True
                duration = 0

            return RoutingDecision(
                item=item,
                action="create_event",
                destination=self.config.calendar_provider,
                duration_minutes=duration if duration > 0 else 0,
                requires_approval=False,
            )

        # Tasks without dates or without calendar go to inbox
        return RoutingDecision(
            item=item,
            action="save_inbox",
            destination=self._inbox_path(item.basket),
            duration_minutes=0,
            requires_approval=False,
        )

    def _route_idea(self, item: CaptureItem) -> RoutingDecision:
        """Route an idea/note item — always to markdown inbox."""
        return RoutingDecision(
            item=item,
            action="save_inbox",
            destination=self._inbox_path(item.basket),
            duration_minutes=0,
            requires_approval=False,
        )

    def _event_duration(self, item: CaptureItem) -> int:
        """Determine appropriate duration for an event."""
        title_lower = item.title.lower()

        # Large events: dinner, party, conference, workshop
        large_keywords = {
            "dinner", "lunch", "party", "conference", "workshop",
            "training", "seminar", "retreat", "wedding", "concert",
            "reception", "festival", "ceremony",
        }
        if any(kw in title_lower for kw in large_keywords):
            return self.config.duration_large_event

        # Meetings and calls
        meeting_keywords = {
            "meeting", "call", "sync", "standup", "stand-up",
            "check-in", "checkin", "review", "discuss", "catch up",
            "catch-up", "1:1", "one on one", "one-on-one",
        }
        if any(kw in title_lower for kw in meeting_keywords):
            return self.config.duration_meeting_call

        # Default: ordinary event/appointment
        return self.config.duration_event_appointment

    def _inbox_path(self, basket: Basket) -> str:
        """Build the markdown inbox file path for a basket."""
        if not self.config.vault_path:
            return f"{self.config.wiki_dir}/{self.config.basket_files.get(basket, 'capture-inbox.md')}"

        vault = self.config.vault_path
        wiki = self.config.wiki_dir
        filename = self.config.basket_files.get(basket, "capture-inbox.md")
        return f"{vault}/{wiki}/{filename}"

    def needs_approval(self, item: CaptureItem) -> tuple[bool, str]:
        """Check if an item requires user approval before acting.

        Returns (needs_approval, reason).
        """
        # Always ask before:
        # - Deleting anything
        # - Sending messages/emails
        # - Storing sensitive personal details

        # Don't need approval for:
        # - Clear, non-conflicting calendar items
        # - Saving to a local markdown inbox
        # - Low-risk, obvious destinations

        if item.basket in (Basket.EVENT_MEETING, Basket.TASK_REMINDER):
            if item.date and item.time:
                return False, ""
            if item.date and not item.time:
                # Date-only without time — still okay, just all-day
                return False, ""

        return False, ""


def route_all(
    items: list[CaptureItem],
    config: Optional[RouterConfig] = None,
    conflict_detector: Optional[ConflictDetector] = None,
) -> list[RoutingDecision]:
    """Route all capture items and return decisions."""
    router = CaptureRouter(config, conflict_detector)
    return [router.route(item) for item in items]
