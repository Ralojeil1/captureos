# Configuration

CaptureOS is intentionally configuration-light. The main behavior lives in the Hermes skills and Markdown templates.

Copy the example config if you want a single place to document your local choices:

```bash
cp config/captureos.config.example.yaml config/captureos.config.yaml
```

Do not commit your local config if it contains private paths, account names, calendar identifiers, or provider details.

## Key settings

- `user.name` — optional display name
- `timezone` — default timezone for relative dates such as “tomorrow”
- `vault.path` — optional Markdown vault/folder path
- `vault.wiki_dir` — subfolder for living notes and inboxes
- `calendar.enabled` — whether calendar actions are allowed
- `calendar.provider` — provider name, such as `google`, `apple`, or `none`
- `calendar.calendar_name` — generic calendar label, not an account ID
- `durations_minutes` — default block lengths
- `baskets` — destination filenames for the three inboxes

## The three baskets

CaptureOS exposes exactly three user-facing baskets:

1. Task / Reminder
2. Event / Meeting
3. Idea / Note

Internal subtypes can exist for routing, but the user should not have to manage more than these three categories.

## Default duration rules

```yaml
durations_minutes:
  meeting_call: 60
  ordinary_event_appointment: 60
  large_event_when_obvious: 120
  timed_task_reminder: 60
```

Date-only tasks/reminders should be all-day. Undated tasks/reminders should default to tomorrow all-day unless your own workflow says otherwise.

## Ask-first policy

Ask before:

- deleting calendar events or notes
- moving/rescheduling existing events unless explicitly requested
- creating calendar items with conflicts or meaningful ambiguity
- sending emails or messages
- saving sensitive personal details
- modifying immutable/raw source files

Act directly when:

- the capture is low-risk and the destination is obvious
- a calendar item is clear and non-conflicting
- updating a local Markdown inbox/template is straightforward

## Storage model

CaptureOS works with plain Markdown. A typical structure is:

```text
YourVault/
├── CUSTOM_COMMANDS.md
└── wiki/
    ├── captureos-layer.md
    ├── capture-tasks-reminders.md
    ├── capture-events-meetings.md
    └── capture-ideas-notes.md
```

You can rename these files, but keep the three-basket model stable.
