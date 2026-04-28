# Public Release Checklist

Use this checklist before changing repository visibility to public.

## Content audit

- [ ] No private names, account handles, emails, phone numbers, or calendar IDs
- [ ] No real client data, CRM rows, chat transcripts, or lead lists
- [ ] No local absolute paths that identify a person or machine
- [ ] No OAuth files, API keys, tokens, passwords, or `.env` files
- [ ] Examples use fictional people and generic scenarios only
- [ ] README explains the project clearly without relying on private context
- [ ] Setup guide works from a clean clone

## Commands

```bash
./scripts/validate.sh
./scripts/secret-scan.sh
git diff --check
```

Recommended external scanners:

```bash
gitleaks detect --source .
trufflehog filesystem . --no-update
```

## Git history

If the repository previously contained private material, scan the full history before going public:

```bash
gitleaks detect --source .
trufflehog git file://$PWD
```

If history contains private material, rewrite history or create a fresh public repository from the cleaned working tree.

## Release polish

- [ ] Repository description is clear
- [ ] Topics/tags are relevant
- [ ] License is present
- [ ] Security guidance is present
- [ ] Install steps are tested
- [ ] Optional patches are clearly marked optional
