"""CaptureOS Conflict Detector — calendar conflict checking.

Detects scheduling conflicts before creating calendar events.
Works with a simple in-memory event store (for testing) or
can be extended to query real calendar APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass
class CalendarEvent:
    """A simple calendar event for conflict checking."""
    title: str
    date: str          # YYYY-MM-DD
    start_time: str    # HH:MM
    end_time: str      # HH:MM
    source: str = ""   # e.g., "google", "apple", "local"


@dataclass
class ConflictResult:
    """Result of a conflict check."""
    has_conflict: bool = False
    reason: str = ""
    conflicting_events: list[CalendarEvent] = field(default_factory=list)


def _time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


class ConflictDetector:
    """Detects scheduling conflicts for calendar events.

    Can work with:
    - An in-memory event store (supplied via events parameter)
    - A real calendar API (by extending the check() method)
    - No events (always returns no conflict)
    """

    def __init__(self, events: Optional[list[CalendarEvent]] = None):
        """Initialize with an optional list of existing events."""
        self._events: list[CalendarEvent] = list(events) if events else []

    def add_event(self, event: CalendarEvent) -> None:
        """Add an event to the store."""
        self._events.append(event)

    def add_events(self, events: list[CalendarEvent]) -> None:
        """Add multiple events to the store."""
        self._events.extend(events)

    @property
    def events(self) -> list[CalendarEvent]:
        """Return a copy of all stored events."""
        return list(self._events)

    def check(
        self,
        event_date: Optional[str],
        event_time: Optional[str],
        duration_minutes: int,
    ) -> ConflictResult:
        """Check if a proposed event conflicts with existing events.

        Args:
            event_date: Date in YYYY-MM-DD format
            event_time: Start time in HH:MM format
            duration_minutes: Duration of the proposed event

        Returns:
            ConflictResult with conflict details
        """
        if not event_date or not event_time or duration_minutes <= 0:
            return ConflictResult()

        if not self._events:
            return ConflictResult()

        proposed_start = _time_to_minutes(event_time)
        proposed_end = proposed_start + duration_minutes

        conflicts = []
        for existing in self._events:
            if existing.date != event_date:
                continue

            exist_start = _time_to_minutes(existing.start_time)
            exist_end = _time_to_minutes(existing.end_time)

            # Overlap detection
            if proposed_start < exist_end and proposed_end > exist_start:
                conflicts.append(existing)

        if conflicts:
            conflict_descriptions = [
                f"'{e.title}' ({e.start_time}-{e.end_time})" for e in conflicts
            ]
            return ConflictResult(
                has_conflict=True,
                reason=f"Conflicts with: {', '.join(conflict_descriptions)}",
                conflicting_events=conflicts,
            )

        return ConflictResult()

    def find_free_slots(
        self,
        target_date: str,
        duration_minutes: int,
        start_hour: int = 8,
        end_hour: int = 20,
    ) -> list[dict]:
        """Find free time slots on a given date.

        Args:
            target_date: Date in YYYY-MM-DD format
            duration_minutes: Required duration
            start_hour: Earliest hour to consider (default: 8)
            end_hour: Latest hour to consider (default: 20)

        Returns:
            List of free slots with start and end times
        """
        # Get existing events sorted by start time
        day_events = sorted(
            [e for e in self._events if e.date == target_date],
            key=lambda e: e.start_time,
        )

        free_slots = []
        current = start_hour * 60
        day_end = end_hour * 60

        for event in day_events:
            event_start = _time_to_minutes(event.start_time)
            event_end = _time_to_minutes(event.end_time)

            if event_start - current >= duration_minutes:
                free_slots.append({
                    "start": _minutes_to_time(current),
                    "end": _minutes_to_time(event_start),
                })
            current = max(current, event_end)

        # Check remaining time after last event
        if day_end - current >= duration_minutes:
            free_slots.append({
                "start": _minutes_to_time(current),
                "end": _minutes_to_time(day_end),
            })

        return free_slots
