# Contributing

Thanks for helping improve CaptureOS.

## Project rules

CaptureOS should stay simple:

1. Task / Reminder
2. Event / Meeting
3. Idea / Note

New integrations are welcome, but they should not add more top-level baskets.

## Development workflow

1. Fork the repo.
2. Create a branch.
3. Make focused changes.
4. Run checks:

```bash
./scripts/validate.sh
./scripts/secret-scan.sh
git diff --check
```

5. Open a pull request with a short explanation and screenshots/examples if useful.

## Privacy rules

Do not include real:

- secrets or tokens
- account identifiers
- calendar IDs
- private notes
- chat transcripts
- client data
- personal contact data

Use fictional examples only.

## Style

- Prefer plain Markdown.
- Keep instructions actionable.
- Keep the three-basket model obvious.
- Mark optional integrations as optional.
