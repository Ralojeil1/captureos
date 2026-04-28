---
name: captureos
description: "Three-basket universal capture router for Hermes Agent: Task / Reminder, Event / Meeting, Idea / Note."
version: 0.3.0
author: CaptureOS contributors
license: MIT
metadata:
  hermes:
    tags: [capture, notes, calendar, productivity, markdown]
    related_skills: [capture, normal]
    required_tools: [terminal, file]
---

# CaptureOS

CaptureOS is a universal capture layer for Hermes Agent and compatible assistant workflows. It classifies natural-language input into exactly three baskets and routes them to the right destination.

## Core principle

Capture anything once. The assistant classifies into one of three baskets and routes to the right destination. Prefer clean living updates over raw dumps.

## Core baskets

Classify every capture into exactly ONE of three top-level user-facing baskets:

1. **Task / Reminder** — todos, follow-ups, promises, deadlines, recurring reminders, scheduled task blocks
2. **Event / Meeting** — calls, meetings, calendar events, trips, appointments, event notes, meeting notes
3. **Idea / Note** — ideas, project notes, people updates, opportunities, journal/reflections, links, durable wiki knowledge, reusable build ideas, dated outputs/runbooks

Subtypes may exist internally for routing, but NEVER expose more than these three baskets to the user.

## How to classify (structured approach)

Use the `captureos` CLI tool for deterministic classification:

```bash
captureos "Dentist tomorrow 3pm"
```

Or call the Python classifier directly:

```python
from captureos import classify
result = classify("Follow up with Sarah Friday 11am")
for item in result.items:
    print(f"{item.basket_label}: {item.title}")
```

**Classification rules (in priority order):**

1. **Explicit prefixes win** — `Task:`, `Reminder:`, `Meeting:`, `Event:`, `Idea:`, `Note:` set the basket directly
2. **Date + time + meeting keyword** → Event / Meeting (e.g., "Call Sam Friday 3pm")
3. **Date + time + task keyword** → Task / Reminder (e.g., "Follow up with Alex Monday 2pm")
4. **Date only, no time** → Task / Reminder, all-day (e.g., "Submit invoice Friday")
5. **No date, idea keyword** → Idea / Note
6. **No date, task keyword** → Task / Reminder
7. **Ambiguous** → Idea / Note (safest default)

## JSON output schema

When using function calling, return structured JSON:

```json
{
  "items": [
    {
      "basket": "event_meeting",
      "title": "Dentist appointment",
      "date": "2026-04-29",
      "time": "15:00",
      "duration_minutes": 60,
      "is_all_day": false,
      "confidence": 0.95,
      "reasoning": "Clear appointment with specific date and time"
    }
  ]
}
```

## Mode commands

- `/capture` = enter Capture Mode for the current session (persists across restarts)
- `/normal` = exit Capture Mode and return to normal assistant behavior

Explicit prefixes still work in normal mode: `Task:`, `Reminder:`, `Meeting:`, `Event:`, `Idea:`, `Capture:`, and `Process this:`.

## Default destinations

**Task / Reminder:**
- Clear dated/timed items → calendar if configured
- Open/undated items → markdown inbox (capture-tasks-reminders.md)

**Event / Meeting:**
- Clear scheduled blocks → calendar if configured
- Meeting notes without time → markdown inbox (capture-events-meetings.md)

**Idea / Note:**
- Prefer strongest existing knowledge-base page when obvious
- Otherwise → markdown inbox (capture-ideas-notes.md)

## Calendar defaults

| Type | Duration |
|------|----------|
| Meeting / Call | 1 hour |
| Ordinary Event / Appointment | 1 hour |
| Large Event (dinner, conference, party) | 2 hours |
| Timed Task / Reminder | 1 hour |
| Date-only Task / Reminder | all-day |
| Undated Task / Reminder | tomorrow all-day |
| Default reminders | 24h and 1h before |

## Ask-first policy

**Ask before:**
- Deleting calendar events or notes
- Moving/rescheduling existing events
- Creating items with conflicts or ambiguity
- Sending emails/messages
- Saving sensitive/private details
- Modifying immutable/raw source files

**Act directly when:**
- Capture is low-risk, destination is obvious
- Calendar item is clear and non-conflicting
- Updating a Markdown inbox is straightforward

## Process this (messy debrief)

For messy notes or transcripts:

1. Split into individual items using `parse_capture_items()`
2. Classify each item into one of three baskets
3. Group proposed actions by basket
4. Preview before applying if many changes
5. Apply approved updates and summarize

## Daily debrief prompts

Ask these questions concisely:
1. What happened today?
2. Who did you speak to?
3. Any promises or follow-ups?
4. Any meetings/events/reminders to calendar?
5. Any ideas worth keeping?
6. Anything for work, clients, projects, or reusable processes?
7. Anything personally important?

Then route each answer into the three baskets.

## Conflict detection

Before creating calendar events, use the ConflictDetector to check for overlaps:

```python
from captureos.conflict import ConflictDetector, CalendarEvent
detector = ConflictDetector(events=existing_events)
conflict = detector.check("2026-04-29", "15:00", 60)
if conflict.has_conflict:
    print(f"Conflict: {conflict.reason}")
```

## Testing

Run the test suite to verify classification accuracy:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
