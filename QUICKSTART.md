# Quickstart

This guide installs CaptureOS into a Hermes Agent setup and creates optional Markdown inbox files for your notes vault.

## 1. Prerequisites

You need:

- Hermes Agent installed and working
- A terminal with `bash`
- A Markdown folder or vault if you want local inbox files
- Optional: a calendar integration configured separately in Hermes

Hermes docs: https://hermes-agent.nousresearch.com/docs

Check Hermes:

```bash
hermes --version
hermes doctor
```

## 2. Clone CaptureOS

```bash
git clone https://github.com/OWNER/captureos.git
cd captureos
```

If you forked the repo, use your fork URL instead.

## 3. Validate the repo

```bash
./scripts/validate.sh
./scripts/secret-scan.sh
```

Expected output:

```text
CaptureOS validation passed.
No obvious sensitive patterns found.
```

## 4. Install the Hermes skills

Install only skills:

```bash
./scripts/install.sh
```

This copies:

```text
skills/capture   -> ~/.hermes/skills/note-taking/capture
skills/normal    -> ~/.hermes/skills/note-taking/normal
skills/captureos -> ~/.hermes/skills/note-taking/captureos
```

If you use a custom Hermes profile or home, set `HERMES_HOME`:

```bash
HERMES_HOME=/path/to/hermes-home ./scripts/install.sh
```

## 5. Install Markdown templates

If you want CaptureOS inbox files in a Markdown vault, pass `--vault`:

```bash
./scripts/install.sh --vault ~/Documents/CaptureVault
```

This creates or updates:

```text
~/Documents/CaptureVault/wiki/capture-tasks-reminders.md
~/Documents/CaptureVault/wiki/capture-events-meetings.md
~/Documents/CaptureVault/wiki/capture-ideas-notes.md
~/Documents/CaptureVault/wiki/captureos-layer.md
~/Documents/CaptureVault/CUSTOM_COMMANDS.md
```

You can use any folder path. Obsidian is optional; plain Markdown works.

## 6. Restart Hermes if needed

For the CLI, start a fresh session:

```bash
hermes
```

For messaging platforms, restart the gateway if you use one:

```bash
hermes gateway restart
```

## 7. Load or use the skills

In a Hermes session, you can explicitly load the main skill:

```text
/skill captureos
```

Then use Capture Mode:

```text
/capture
```

Send normal messages:

```text
Dentist tomorrow 3pm
Follow up with Jordan Friday 11am
Idea: reusable onboarding checklist for new clients
```

Exit Capture Mode:

```text
/normal
```

## 8. Optional: configure native slash commands

Depending on your Hermes version, skill commands may already work. If you want `/capture` and `/normal` to appear as native slash commands in a gateway menu, review the optional patch:

```text
docs/native-hermes-commands.md
```

Apply it only if you are comfortable maintaining a local Hermes patch.

## 9. Optional: calendar, email, and messaging integrations

CaptureOS does not ship credentials, tokens, or account access. Configure providers through Hermes or your own automation layer.

See the full integration guide:

```text
SETUP_INTEGRATIONS.md
```

It covers:

- Google Calendar / Google Workspace OAuth
- Gmail access
- IMAP/SMTP email through Himalaya
- Hermes messaging gateway setup
- safe test flow and security notes

## 10. Try a full test

```text
/capture
Dentist tomorrow 3pm
Call Alex Friday 10am about the launch
Remember to renew passport next Monday
Idea: turn weekly notes into a client status report
/normal
```

Expected routing:

```text
Event / Meeting: Dentist tomorrow 3pm
Event / Meeting: Call Alex Friday 10am about the launch
Task / Reminder: Renew passport next Monday
Idea / Note: Weekly notes to client status report
```
