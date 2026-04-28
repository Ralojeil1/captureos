"""CaptureOS Classifier — deterministic and LLM-based classification.

Core JSON schema for structured classification output:

{
    "basket": "task_reminder" | "event_meeting" | "idea_note",
    "title": str,
    "date": "YYYY-MM-DD" | null,
    "time": "HH:MM" | null,
    "duration_minutes": int,
    "is_all_day": bool,
    "confidence": float (0.0-1.0),
    "reasoning": str
}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional

# ── Schema ──────────────────────────────────────────────────────────

class Basket(str, Enum):
    TASK_REMINDER = "task_reminder"
    EVENT_MEETING = "event_meeting"
    IDEA_NOTE = "idea_note"


@dataclass
class CaptureItem:
    """A single classified capture item."""
    basket: Basket
    title: str
    date: Optional[str] = None       # YYYY-MM-DD
    time: Optional[str] = None       # HH:MM (24h)
    duration_minutes: int = 60
    is_all_day: bool = False
    confidence: float = 1.0
    reasoning: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["basket"] = self.basket.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @property
    def basket_label(self) -> str:
        return {
            Basket.TASK_REMINDER: "Task / Reminder",
            Basket.EVENT_MEETING: "Event / Meeting",
            Basket.IDEA_NOTE: "Idea / Note",
        }[self.basket]

    @property
    def is_timed(self) -> bool:
        return self.time is not None and not self.is_all_day


@dataclass
class CaptureResult:
    """Result of classifying one or more input strings."""
    items: list[CaptureItem] = field(default_factory=list)
    raw_input: str = ""

    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "raw_input": self.raw_input,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        lines = []
        for item in self.items:
            timing = ""
            if item.date:
                timing = f" {item.date}"
                if item.time:
                    timing += f" {item.time}"
                    timing += f" ({item.duration_minutes}min)"
            lines.append(f"[{item.basket_label}] {item.title}{timing}")
        return "\n".join(lines)


# ── Classification Schema (for LLM function calling) ────────────────

# ── Heuristic Classification ────────────────────────────────────────
# These functions implement the deterministic classification rules.
# They can work standalone (without an LLM) for common patterns.

def _default_duration(basket: Basket, title: str, config=None) -> int:
    """Get default duration based on basket and title keywords."""
    if basket == Basket.EVENT_MEETING:
        large_kw = {"dinner", "party", "conference", "workshop", "reception", "wedding"}
        if any(kw in title.lower() for kw in large_kw):
            return 120
        return 60
    elif basket == Basket.TASK_REMINDER:
        return 60
    return 0


def classify_single(
    text: str,
    reference_date: Optional[date] = None,
    config=None,
) -> CaptureItem:
    """Classify a single natural-language input into a CaptureItem using heuristics.

    This is a deterministic classifier that works without an LLM.
    For ambiguous cases, use an LLM with CLASSIFY_FUNCTION_SCHEMA.

    Classification rules (in priority order):
    1. Explicit prefix (Task:, Meeting:, Idea:) → sets basket
    2. Date + time + meeting keyword → Event/Meeting
    3. Date + time + task keyword → Task/Reminder  
    4. Date only + event keyword → Event/Meeting (all-day)
    5. Date only + task keyword → Task/Reminder (all-day)
    6. Date only → Task/Reminder (all-day)
    7. Idea/note keyword → Idea/Note
    8. Task keyword → Task/Reminder
    9. Ambiguous → Idea/Note (safe default)
    """
    from captureos.parser import detect_explicit_prefix, strip_prefix, extract_date_time

    if reference_date is None:
        reference_date = date.today()

    cleaned = strip_prefix(text)
    explicit = detect_explicit_prefix(text)
    dt_info = extract_date_time(cleaned, reference_date)

    has_date = dt_info["has_date"]
    has_time = dt_info["has_time"]

    # 1. Explicit prefix wins
    if explicit:
        basket = Basket(explicit)
        return CaptureItem(
            basket=basket,
            title=cleaned,
            date=dt_info["date"],
            time=dt_info["time"],
            duration_minutes=_default_duration(basket, cleaned, config),
            is_all_day=dt_info["is_all_day"],
            confidence=1.0,
            reasoning=f"Explicit prefix: {explicit}",
        )

    cleaned_lower = cleaned.lower()

    # Recurring patterns (e.g. "every Monday") → idea/note for now
    if re.search(r'\bevery\b', cleaned_lower):
        return CaptureItem(
            basket=Basket.IDEA_NOTE,
            title=cleaned,
            date=dt_info["date"],
            time=dt_info["time"],
            confidence=0.85,
            reasoning="Recurring pattern detected, saving as idea/note",
        )

    # 2. Date + time present
    if has_date and has_time:
        meeting_kw = {"meeting", "call", "sync", "standup", "appointment",
                      "dentist", "doctor", "lunch", "dinner", "coffee", "breakfast"}
        if any(kw in cleaned_lower for kw in meeting_kw):
            return CaptureItem(
                basket=Basket.EVENT_MEETING,
                title=cleaned,
                date=dt_info["date"],
                time=dt_info["time"],
                duration_minutes=_default_duration(Basket.EVENT_MEETING, cleaned, config),
                is_all_day=False,
                confidence=0.9,
                reasoning="Meeting/event keyword with specific time",
            )

        task_kw = {"follow up", "follow-up", "remind", "remember", "submit",
                   "send", "finish", "complete", "review", "check", "prepare"}
        if any(kw in cleaned_lower for kw in task_kw):
            return CaptureItem(
                basket=Basket.TASK_REMINDER,
                title=cleaned,
                date=dt_info["date"],
                time=dt_info["time"],
                duration_minutes=60,
                is_all_day=False,
                confidence=0.85,
                reasoning="Task keyword with specific date/time",
            )

        # Default: timed → event
        return CaptureItem(
            basket=Basket.EVENT_MEETING,
            title=cleaned,
            date=dt_info["date"],
            time=dt_info["time"],
            duration_minutes=60,
            is_all_day=False,
            confidence=0.7,
            reasoning="Timed item, defaulting to event",
        )

    # 3. Date only (no time)
    if has_date and not has_time:
        event_kw = {"meeting", "call", "dentist", "doctor", "appointment",
                    "lunch", "dinner", "party", "conference"}
        if any(kw in cleaned_lower for kw in event_kw):
            return CaptureItem(
                basket=Basket.EVENT_MEETING,
                title=cleaned,
                date=dt_info["date"],
                time=None,
                duration_minutes=0,
                is_all_day=True,
                confidence=0.8,
                reasoning="Event keyword with date only, all-day",
            )

        task_kw = {"follow up", "remind", "remember", "submit", "send",
                   "finish", "complete", "task", "todo", "deadline", "prepare"}
        if any(kw in cleaned_lower for kw in task_kw):
            return CaptureItem(
                basket=Basket.TASK_REMINDER,
                title=cleaned,
                date=dt_info["date"],
                time=None,
                duration_minutes=0,
                is_all_day=True,
                confidence=0.85,
                reasoning="Task keyword with date, all-day task",
            )

        # Default date-only → task (all-day reminder)
        return CaptureItem(
            basket=Basket.TASK_REMINDER,
            title=cleaned,
            date=dt_info["date"],
            time=None,
            duration_minutes=0,
            is_all_day=True,
            confidence=0.65,
            reasoning="Date-only item, defaulting to all-day task",
        )

    # 4. Time present but no date — check for meeting/event keywords
    if has_time and not has_date:
        meeting_kw = {"meeting", "call", "sync", "standup", "appointment",
                      "dentist", "doctor", "lunch", "dinner", "coffee", "breakfast"}
        if any(kw in cleaned_lower for kw in meeting_kw):
            return CaptureItem(
                basket=Basket.EVENT_MEETING,
                title=cleaned,
                date=None,
                time=dt_info["time"],
                duration_minutes=_default_duration(Basket.EVENT_MEETING, cleaned, config),
                is_all_day=False,
                confidence=0.8,
                reasoning="Meeting/event keyword with time, no date specified",
            )

    # 5. No date — classify by keywords
    idea_kw = {"idea", "note", "think", "maybe", "someday", "consider",
               "reflect", "journal", "learn", "explore", "research"}
    if any(kw in cleaned_lower for kw in idea_kw):
        return CaptureItem(
            basket=Basket.IDEA_NOTE,
            title=cleaned,
            confidence=0.9,
            reasoning="Idea/note keyword detected",
        )

    task_kw = {"follow up", "remind", "remember", "task", "todo", "check"}
    if any(kw in cleaned_lower for kw in task_kw):
        return CaptureItem(
            basket=Basket.TASK_REMINDER,
            title=cleaned,
            confidence=0.7,
            reasoning="Task keyword, no date specified",
        )

    # Default: idea/note (safest basket)
    return CaptureItem(
        basket=Basket.IDEA_NOTE,
        title=cleaned,
        confidence=0.5,
        reasoning="No clear signal, defaulting to idea/note",
    )


def classify(
    text: str,
    config=None,
    reference_date: Optional[date] = None,
) -> "CaptureResult":
    """Classify natural-language input into capture items.

    Handles both single and multi-item input by splitting first.
    """
    from captureos.parser import parse_capture_items

    parsed_items = parse_capture_items(text, reference_date)
    items = []
    for parsed in parsed_items:
        item = classify_single(parsed["raw_text"], reference_date, config)
        items.append(item)

    return CaptureResult(items=items, raw_input=text)


def classify_multi(
    texts: list[str],
    config=None,
    reference_date: Optional[date] = None,
) -> list[CaptureResult]:
    """Classify multiple independent text inputs."""
    return [classify(t, config, reference_date) for t in texts]


CLASSIFY_FUNCTION_SCHEMA = {
    "name": "classify_capture",
    "description": "Classify natural-language input into exactly one of three baskets: "
                   "task_reminder (todos, follow-ups, deadlines, promises), "
                   "event_meeting (calls, meetings, appointments, calendar events), "
                   "idea_note (ideas, notes, reflections, links, project knowledge).",
    "parameters": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "One or more classified capture items extracted from the input",
                "items": {
                    "type": "object",
                    "properties": {
                        "basket": {
                            "type": "string",
                            "enum": ["task_reminder", "event_meeting", "idea_note"],
                            "description": "The classification basket"
                        },
                        "title": {
                            "type": "string",
                            "description": "Concise title for the captured item"
                        },
                        "date": {
                            "type": "string",
                            "description": "Date in YYYY-MM-DD format, or null if no date detected"
                        },
                        "time": {
                            "type": "string",
                            "description": "Time in HH:MM 24-hour format, or null if no time detected"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration in minutes. Default: 60 for meetings/calls/events/timed tasks, 120 for large events (dinner, conference, party). All-day when no time provided for date-only items."
                        },
                        "is_all_day": {
                            "type": "boolean",
                            "description": "True for date-only items with no specific time"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score from 0.0 to 1.0"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of classification reasoning"
                        },
                    },
                    "required": ["basket", "title", "confidence", "reasoning"]
                }
            }
        },
        "required": ["items"]
    }
}
