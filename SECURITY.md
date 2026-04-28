# Security and Privacy

CaptureOS is meant to publish the system, not private data.

Before sharing or publishing a CaptureOS setup, remove:

- OAuth tokens and API keys
- `.env` files
- account names, usernames, and personal email addresses
- calendar IDs and private event IDs
- phone numbers and messaging IDs
- Telegram, Discord, Slack, WhatsApp, or other bot tokens
- local absolute paths that identify a person or machine
- private vault contents
- raw chat transcripts
- client data, CRM exports, and lead lists
- screenshots or logs that expose personal information

## Recommended pre-public checklist

Run the built-in checks:

```bash
./scripts/validate.sh
./scripts/secret-scan.sh
```

Also run at least one dedicated scanner:

```bash
# Option A: gitleaks
brew install gitleaks
gitleaks detect --source . --no-git

# Option B: trufflehog
brew install trufflehog
trufflehog filesystem . --no-update
```

If the repo has previous private commits, scan git history too:

```bash
gitleaks detect --source .
trufflehog git file://$PWD
```

## Design principle

Publish:

- generic skills
- templates
- examples
- setup instructions
- safe scripts

Do not publish:

- real user data
- real calendars
- real accounts
- real secrets
- private assistant transcripts
- private knowledge-base pages

## Reporting issues

If you find a privacy or security issue in CaptureOS, open a private security advisory or contact the maintainer privately before posting details publicly.
