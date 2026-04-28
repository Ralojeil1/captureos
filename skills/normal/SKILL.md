---
name: normal
description: Exit CaptureOS Capture Mode and return to normal assistant behavior.
version: 0.2.0
author: CaptureOS contributors
license: MIT
metadata:
  hermes:
    tags: [capture, productivity, mode]
    related_skills: [captureos, capture]
---

# Normal Mode

The user invoked `/normal`, meaning: exit CaptureOS Capture Mode for this session.

## Behavior

1. Stop treating every short message as a capture by default.
2. Return to normal assistant behavior: answer, reason, code, research, or act based on explicit requests.
3. Still recognize explicit capture/calendar language such as `Capture:`, `Task:`, `Reminder:`, `Meeting:`, `Event:`, `Idea:`, or `Process this:`.
4. If the user later invokes `/capture`, resume Capture Mode.

**Important: Persist the mode change:**

```bash
captureos --normal
```

## Check current mode

```bash
captureos --status
```
