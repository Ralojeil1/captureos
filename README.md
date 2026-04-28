# CaptureOS

![CaptureOS visual overview](assets/captureos-hero.svg)

CaptureOS is a lightweight, private-first capture router for Hermes Agent.

It gives your AI assistant one simple job: take messy natural-language input and route it into the right place — a task/reminder, a calendar event/meeting, or an idea/note.

```text
Input:  Dentist tomorrow 3pm
Output: Event / Meeting → create a 1-hour calendar event for tomorrow at 3pm

Input:  Idea: build a weekly client report generator
Output: Idea / Note → save to the idea inbox or the best matching project note
```

CaptureOS turns quick texts, voice notes, meeting notes, pasted ideas, and reminders into exactly one of three simple baskets:

1. Task / Reminder
2. Event / Meeting
3. Idea / Note

The point is not to create another dumping ground. CaptureOS gives an AI assistant a clean operating model for deciding what something is, where it belongs, and when it should ask before acting.

## Why CaptureOS?

Most capture systems either over-classify everything or let notes pile up forever. CaptureOS keeps the user-facing model intentionally small:

- Tasks and reminders are things to do or remember.
- Events and meetings are things that occupy time on a calendar.
- Ideas and notes are durable knowledge, context, links, reflections, or project material.

Everything else is an internal subtype, not another basket the user has to manage.

## What it includes

- **Python package** (`pip install captureos`) — deterministic 9-rule classifier, multi-item parser, conflict detector
- **Standalone CLI** (`captureos "Dentist tomorrow 3pm"`) — no Hermes required
- **Structured JSON output** — use `--json` for machine-readable results or LLM function calling
- **Telegram bot** (`captureos --telegram`) — polling-based bot with /capture, /normal, /status, /inbox
- **Google Calendar integration** (`captureos "..." --gcal`) — write events, check conflicts, 3 auth strategies
- **Markdown inbox writer** — classifies → writes → reads back markdown files
- **Conflict detection** — overlap checking + free-slot search before creating events
- **Persistent capture mode** — survives session restarts via `~/.captureos/state.json`
- **Date/time parser** — 25+ formats: named dates, slash dates, relative offsets, noon/midnight, day-of-week
- **Hermes Agent skills** for `/capture`, `/normal`, and the core `captureos` routing rules
- **Comprehensive test suite** — 149+ pytest tests covering all modules
- **Validation and secret-scan scripts** for public-release readiness

## Core commands

```text
/capture
```

Enter Capture Mode. Short natural-language messages are treated as captures by default.

```text
/normal
```

Exit Capture Mode and return to normal assistant behavior.

Explicit prefixes such as `Task:`, `Reminder:`, `Meeting:`, `Event:`, `Idea:`, `Capture:`, and `Process this:` can still be used outside Capture Mode.

## How it works

### Example 1: task / reminder

Input:

```text
Follow up with Sarah Friday 11am about the proposal
```

CaptureOS classifies it as:

```text
Basket: Task / Reminder
Default duration: 1 hour if placed on a calendar
Action: create a reminder/task block if calendar integration is configured, otherwise save to the Task / Reminder inbox
```

### Example 2: event / meeting

Input:

```text
Dentist tomorrow 3pm
```

CaptureOS classifies it as:

```text
Basket: Event / Meeting
Default duration: 1 hour
Action: create a calendar event if the time is clear and there is no conflict
```

### Example 3: idea / note

Input:

```text
Idea: build a reusable onboarding agent that turns client calls into implementation plans
```

CaptureOS classifies it as:

```text
Basket: Idea / Note
Action: save to the strongest matching knowledge-base page, or the Idea / Note inbox if no better destination exists
```

### Example 4: messy debrief

Input:

```text
Process this: met Jordan today. He wants the new landing page by Thursday. Also had an idea for a simple weekly client report generator.
```

CaptureOS extracts:

```text
Task / Reminder: deliver or follow up on the landing page by Thursday
Event / Meeting: met Jordan today
Idea / Note: weekly client report generator idea
```

## Default timing rules

- Timed Task / Reminder: 1 hour
- Date-only Task / Reminder: all-day
- Undated Task / Reminder: tomorrow all-day
- Meeting / Call: 1 hour
- Ordinary Event / Appointment: 1 hour
- Large Event: 2 hours only when context clearly implies a longer block
- Calendar reminders: 24 hours and 1 hour before, when supported by the calendar provider

## Ask-first policy

CaptureOS is designed to act when the action is obvious and low risk, and ask when it matters.

Act directly when:

- the capture has a clear destination
- a calendar item is clear and non-conflicting
- saving to a local Markdown inbox is straightforward

Ask first before:

- deleting anything
- rescheduling existing events
- creating events when there is a conflict or meaningful ambiguity
- sending messages or emails
- storing sensitive personal details
- modifying raw/immutable evidence files

## Quick setup

### Python package (standalone)

```bash
pip install captureos                  # core package
pip install captureos[all]             # with Telegram + Google Calendar
captureos "Dentist tomorrow 3pm"
captureos --json "Meeting Monday 10am"
captureos --multi "Call Alex Friday. Idea: build a dashboard."
captureos --write "Idea: build a weekly report" --vault ~/Documents/Vault
captureos "Dentist tomorrow 3pm" --gcal           # Google Calendar (needs auth)
captureos --telegram                              # Start Telegram bot
```

### Telegram bot

```bash
export TELEGRAM_BOT_TOKEN="your_token_from_BotFather"
captureos --telegram
```

Bot commands in Telegram:
- `/capture` — all messages classified as captures
- `/normal` — back to normal chat
- `/status` — current mode
- `/inbox` — recent captures
- `/help` — usage

### Google Calendar

```bash
# One-command setup wizard (recommended):
captureos-gcal-setup

# Or quick setup with service account:
captureos-gcal-setup --service-account --project YOUR_PROJECT_ID

# Or with existing OAuth client secret:
captureos-gcal-setup --client-secret ~/Downloads/client_secret.json

# Then create events:
captureos "Dentist tomorrow 3pm" --gcal
captureos "Meeting Monday 10am" --gcal --check-conflicts
```

The setup wizard walks you through 3 auth options:

| Method | Browser needed? | Warning? | Best for |
|--------|----------------|----------|----------|
| Google OAuth (default) | Once | Shows "unverified app" (expected) | Personal use, any device |
| Service Account | Never | None | Servers, Raspberry Pi, headless |
| Custom OAuth Client | Once | None (it's your own app) | Your own GCP project |

**About the "unverified app" warning (Google OAuth method):**

After signing in, Google will show:

```
╔══════════════════════════════════════════╗
║  ⚠ Google hasn't verified this app     ║
║                                          ║
║  This app is requesting access to your   ║
║  Google Calendar. Google hasn't reviewed ║
║  this app yet.                           ║
║                                          ║
║  [Advanced]                  [Back]      ║
╚══════════════════════════════════════════╝
```

This is **completely normal** and happens for hundreds of legitimate developer tools (gcloud CLI, rclone, Thunderbird, etc.). Here's why:

- **Google charges $15,000-$75,000 for "app verification"** — open-source tools can't afford this
- The warning means Google hasn't *reviewed* the app, NOT that it's dangerous
- You're logging into **your own Google account** with **Google's official SDK client** — there is zero risk

**What to do:** Click **"Advanced"** (bottom-left corner) → Click **"Go to Google Auth Library (unsafe)"** → Approve Calendar access → Done. The token is saved and works forever.

**To avoid the warning entirely:** Use a **Service Account** (no browser, no warning) or create your own **Custom OAuth Client** in the Google Cloud Console (no warning because it's your own app).

The wizard explains all of this interactively — just run `captureos-gcal-setup`.

### Hermes Agent skill pack

```bash
git clone https://github.com/Ralojeil1/captureos.git
cd captureos
./scripts/install.sh --vault ~/Documents/CaptureVault
```

Then restart Hermes or its messaging gateway if needed, and try:

```text
/capture
Dentist tomorrow 3pm
Idea: a tiny habit tracker that uses voice notes
/normal
```

For the full setup flow, see `QUICKSTART.md`. For calendar, email, and messaging access, see `SETUP_INTEGRATIONS.md`.

## Repository structure

```text
CaptureOS/
├── src/captureos/            # Python package
│   ├── __init__.py
│   ├── classifier.py         # Deterministic + LLM classification
│   ├── parser.py             # Multi-item NL parser, date/time extraction
│   ├── router.py             # Routes classified items to destinations
│   ├── writer.py             # Markdown inbox file I/O
│   ├── state.py              # Persistent capture mode state
│   ├── conflict.py           # Calendar conflict detection
│   ├── telegram_bot.py       # Telegram polling bot
│   ├── gcal_writer.py        # Google Calendar event writer
│   └── cli.py                # Standalone CLI entry point
├── tests/                    # 149+ pytest tests
├── skills/                   # Hermes skills
│   ├── capture/
│   ├── normal/
│   └── captureos/
├── templates/                # Markdown inbox and command templates
├── config/                   # Example configuration
├── examples/                 # Example capture flows
├── scripts/                  # install, validate, and secret scan scripts
├── pyproject.toml            # Package metadata
└── docs/                     # optional integration notes
```

## Security

CaptureOS is private-first by design. It ships reusable instructions, templates, examples, and scripts — never credentials or private user data.

Before using it with real accounts, read `SECURITY.md` and keep tokens, OAuth files, account identifiers, calendar IDs, private vaults, and contact data out of the repository.

Maintainers can run the included checks with:

```bash
./scripts/validate.sh
./scripts/secret-scan.sh
```

## Classification rules

The deterministic classifier uses a 9-rule priority system:

1. **Explicit prefix** — `Task:`, `Meeting:`, `Idea:`, etc. set the basket directly
2. **Date + time + meeting keyword** → Event / Meeting
3. **Date + time + task keyword** → Task / Reminder
4. **Time only + meeting keyword** → Event / Meeting (e.g., "Conference call 2pm")
5. **Date only + event keyword** → Event / Meeting (all-day)
6. **Date only + task keyword** → Task / Reminder (all-day)
7. **Date only, no keyword** → Task / Reminder (all-day, safest for dated items)
8. **Recurring pattern** ("every Monday") → Idea / Note
9. **No clear signal** → Idea / Note (safest default)

For programmatic use, import the classifier:

```python
from captureos import classify
result = classify("Dentist tomorrow 3pm")
for item in result.items:
    print(f"{item.basket_label}: {item.title} — {item.date} {item.time}")
```

## API

```python
from captureos import classify, classify_multi
from captureos.classifier import classify_single, CaptureItem, Basket, CLASSIFY_FUNCTION_SCHEMA
from captureos.router import CaptureRouter, RouterConfig
from captureos.writer import write_to_inbox, read_inbox
from captureos.state import is_capture_mode, set_capture_mode
from captureos.conflict import ConflictDetector, CalendarEvent
from captureos.gcal_writer import GCalWriter
from captureos.telegram_bot import TelegramCaptureBot
```

## Status

v0.3.0 — Production-ready classification with optional Telegram + Google Calendar integrations. The core engine is deterministic and tested; cloud integrations require user-provided credentials.

## License

MIT. See `LICENSE`.
