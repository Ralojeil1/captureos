# Quickstart

CaptureOS can be used two ways: as a standalone Python CLI, or as a Hermes Agent skill pack.

## Option A: Standalone Python CLI (recommended)

### 1. Install

```bash
# Core package
pip install captureos

# With Telegram + Google Calendar support
pip install captureos[all]
```

### 2. Try it

```bash
captureos "Dentist tomorrow 3pm"
captureos --json "Meeting Monday 10am"
captureos --multi "Call Alex Friday. Idea: build a dashboard."
```

### 3. Write to markdown inbox

```bash
captureos --write "Task: follow up with Sarah" --vault ~/Documents/CaptureVault
captureos --inbox tasks --vault ~/Documents/CaptureVault
```

### 4. Telegram bot

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
captureos --telegram
```

Then message your bot:
```
/capture
Dentist tomorrow 3pm
Call Alex Friday 10am
Idea: build a dashboard
/normal
```

### 5. Google Calendar

```bash
# Auth (pick one):
gcloud auth application-default login \
  --scopes="https://www.googleapis.com/auth/calendar.events,https://www.googleapis.com/auth/cloud-platform"

# Or service account:
export GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/key.json

# Create events:
captureos "Dentist tomorrow 3pm" --gcal
captureos "Meeting Monday 10am" --gcal --check-conflicts
```

### 6. Python API

```python
from captureos import classify
from captureos.writer import write_to_inbox

result = classify("Dentist tomorrow 3pm")
for item in result.items:
    print(f"{item.basket_label}: {item.title}")
    write_to_inbox(item, "~/Vault/wiki/capture-events-meetings.md")
```

### 7. Run tests

```bash
pip install captureos[dev]
pytest tests/ -v
```

## Option B: Hermes Agent skill pack

### 1. Prerequisites

- Hermes Agent installed and working
- A terminal with `bash`
- A Markdown folder or vault if you want local inbox files

### 2. Clone CaptureOS

```bash
git clone https://github.com/Ralojeil1/captureos.git
cd captureos
```

### 3. Validate the repo

```bash
./scripts/validate.sh
./scripts/secret-scan.sh
```

Expected output:
```
CaptureOS validation passed.
No obvious sensitive patterns found.
```

### 4. Install the Hermes skills

```bash
./scripts/install.sh
```

This copies:
```
skills/capture   -> ~/.hermes/skills/note-taking/capture
skills/normal    -> ~/.hermes/skills/note-taking/normal
skills/captureos -> ~/.hermes/skills/note-taking/captureos
```

If you use a custom Hermes profile or home, set `HERMES_HOME`:

```bash
HERMES_HOME=/path/to/hermes-home ./scripts/install.sh
```

### 5. Install Markdown templates

If you want CaptureOS inbox files in a Markdown vault, pass `--vault`:

```bash
./scripts/install.sh --vault ~/Documents/CaptureVault
```

This creates:
```
~/Documents/CaptureVault/wiki/capture-tasks-reminders.md
~/Documents/CaptureVault/wiki/capture-events-meetings.md
~/Documents/CaptureVault/wiki/capture-ideas-notes.md
~/Documents/CaptureVault/wiki/captureos-layer.md
~/Documents/CaptureVault/CUSTOM_COMMANDS.md
```

You can use any folder path. Obsidian is optional; plain Markdown works.

### 6. Restart Hermes if needed

```bash
hermes gateway restart
```

### 7. Try it in Hermes

```text
/capture
Dentist tomorrow 3pm
Call Alex Friday 10am about the launch
Remember to renew passport next Monday
Idea: turn weekly notes into a client status report
/normal
```

Expected routing:
```
Event / Meeting: Dentist tomorrow 3pm
Event / Meeting: Call Alex Friday 10am about the launch
Task / Reminder: Renew passport next Monday
Idea / Note: Weekly notes to client status report
```

## Both options: configure calendar + email

CaptureOS does not ship credentials. Configure providers through Hermes or your own automation layer.

See the integration guide: `SETUP_INTEGRATIONS.md`

It covers:
- Google Calendar / Google Workspace OAuth
- Gmail access
- IMAP/SMTP email through Himalaya
- Hermes messaging gateway setup
- Safe test flow and security notes
