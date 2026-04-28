---
name: capture
description: Enter CaptureOS Capture Mode. Short natural-language messages are treated as captures and routed into three baskets.
version: 0.2.0
author: CaptureOS contributors
license: MIT
metadata:
  hermes:
    tags: [capture, productivity, notes, calendar]
    related_skills: [captureos, normal]
---

# Capture Mode

The user invoked `/capture`, meaning: enter CaptureOS Capture Mode for this session.

## Behavior

Until the user invokes `/normal` or clearly asks to stop capture mode:

1. Treat short natural-language messages as captures by default, not questions.
2. Use the classifier tool (`captureos` CLI or Python API) for deterministic routing.
3. Route every capture into exactly one of three top-level baskets:
   - Task / Reminder
   - Event / Meeting
   - Idea / Note
4. If one message contains multiple items, split and route each independently.
5. Do not expose extra top-level categories to the user.
6. Ask only when ambiguity materially changes the action.

**Important: Persist capture mode state** so it survives session restarts:

```bash
captureos --capture
```

## Classification priority

1. **Explicit prefix** (Task:, Meeting:, Idea:) → sets basket directly
2. **Date + time + meeting keyword** → Event / Meeting
3. **Date + time + task keyword** → Task / Reminder
4. **Date only** → Task / Reminder (all-day)
5. **Idea/note keyword** → Idea / Note
6. **No clear signal** → Idea / Note (safe default)

## Default durations

| Type | Duration |
|------|----------|
| Timed Task / Reminder | 1 hour |
| Date-only Task / Reminder | all-day |
| Undated Task / Reminder | tomorrow all-day |
| Meeting / Call | 1 hour |
| Ordinary Event / Appointment | 1 hour |
| Large Event (dinner, party) | 2 hours |

## Response style

Be concise. Confirm what was captured and where it went. Use this format:

```
📅 [Event / Meeting] Dentist — tomorrow 15:00 (60min)
☐ [Task / Reminder] Follow up with Sarah — Friday 11:00 (60min)
💡 [Idea / Note] Build reusable onboarding dashboard
```
