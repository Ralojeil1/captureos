# Setup: Calendars, Email, and Messaging

CaptureOS is the routing layer. It does not include credentials, tokens, or account access.

To let an assistant create calendar events, read/send email, or run from messaging apps, configure those integrations in Hermes Agent or in your own automation layer.

## Recommended setup path

1. Install Hermes Agent.
2. Install CaptureOS skills.
3. Create optional Markdown inbox files.
4. Connect a calendar provider if you want events/reminders created automatically.
5. Connect email only if you want email-aware capture or send/reply workflows.
6. Connect a messaging gateway if you want to capture from Telegram, Discord, Slack, etc.
7. Test with safe examples before using real data.

## 1. Hermes Agent

Install and verify Hermes:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
hermes doctor
```

Run setup if needed:

```bash
hermes setup
```

## 2. CaptureOS

```bash
git clone https://github.com/OWNER/captureos.git
cd captureos
./scripts/install.sh --vault ~/Documents/CaptureVault
```

Restart Hermes or its gateway after installation:

```bash
hermes gateway restart
```

## 3. Calendar access

Calendar access is optional.

Use it if you want captures such as `Dentist tomorrow 3pm` or `Call Sam Friday 10am` to become calendar items.

### Google Calendar through Hermes Google Workspace

In Hermes, install/enable the Google Workspace skill if needed, then run its OAuth setup.

Typical flow:

```text
/skill google-workspace
```

Then follow the skill's setup instructions:

```bash
GSETUP="python3 ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/setup.py"
$GSETUP --check
```

If not authenticated, create a Google Cloud OAuth Desktop client, download the client secret JSON, then run:

```bash
$GSETUP --client-secret /path/to/client_secret.json
$GSETUP --auth-url --services calendar
$GSETUP --auth-code "PASTE_THE_REDIRECT_URL_OR_CODE"
$GSETUP --check
```

For both Gmail and Calendar:

```bash
$GSETUP --auth-url --services email,calendar
```

Do not commit the OAuth JSON file or generated token file.

### Calendar behavior CaptureOS expects

- Clear, non-conflicting calendar items can be created directly.
- Ask before conflicts, deletes, reschedules, or ambiguous events.
- Default reminders: 24 hours and 1 hour before, if supported.
- Ordinary events, appointments, calls, meetings, and timed reminders default to 1 hour.
- Large events default to 2 hours only when context clearly implies it.

## 4. Email access

Email access is optional.

Use it if you want workflows like:

- capture follow-ups from email
- summarize unread emails
- draft replies
- send emails after confirmation

CaptureOS itself should not send emails silently. Sending should require explicit user approval unless a separate workflow gives clear standing permission.

### Option A: Gmail through Hermes Google Workspace

Use the same Google Workspace setup as above with email scopes:

```bash
$GSETUP --auth-url --services email
```

Or for both email and calendar:

```bash
$GSETUP --auth-url --services email,calendar
```

### Option B: IMAP/SMTP through Himalaya

Install Himalaya:

```bash
brew install himalaya
```

Configure an account:

```bash
himalaya account configure
```

Verify:

```bash
himalaya account list
himalaya envelope list --page-size 5
```

For Gmail with IMAP/SMTP, use an app password or your provider's recommended secure authentication method. Store passwords in a keychain, password manager, or secure command — not in the repository.

## 5. Messaging gateway

If you want to capture from Telegram, Discord, Slack, or another chat app, configure the Hermes gateway:

```bash
hermes gateway setup
hermes gateway restart
hermes gateway status
```

Then test from your messaging app:

```text
/capture
Dentist tomorrow 3pm
Idea: a better weekly planning ritual
/normal
```

Some platforms cache slash-command menus. If commands do not appear immediately, restart the gateway and reopen the chat.

## 6. Safe test plan

Before using real accounts heavily, test with harmless inputs:

```text
/capture
Dentist tomorrow 3pm
Call Taylor Friday 10am
Remember to buy batteries Saturday
Idea: simple meal planning template
/normal
```

Confirm that:

- events go to the calendar only when configured
- notes go to the Markdown inboxes
- ambiguous/conflicting items ask first
- email sending never happens without approval

## Security notes

Never commit:

- `.env` files
- OAuth client secrets
- OAuth tokens
- app passwords
- account emails
- calendar IDs
- private contact data
- real message exports

Run before publishing:

```bash
./scripts/validate.sh
./scripts/secret-scan.sh
```
