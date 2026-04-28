#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

required=(
  README.md
  QUICKSTART.md
  CONFIGURATION.md
  SECURITY.md
  LICENSE
  skills/capture/SKILL.md
  skills/normal/SKILL.md
  skills/captureos/SKILL.md
  templates/capture-tasks-reminders.md
  templates/capture-events-meetings.md
  templates/capture-ideas-notes.md
  templates/captureos-layer.md
  config/captureos.config.example.yaml
)

for f in "${required[@]}"; do
  [[ -f "$ROOT/$f" ]] || { echo "Missing $f" >&2; exit 1; }
done

for basket in "Task / Reminder" "Event / Meeting" "Idea / Note"; do
  if ! grep -q "$basket" "$ROOT/skills/captureos/SKILL.md"; then
    echo "Missing basket in captureos skill: $basket" >&2
    exit 1
  fi
  if ! grep -q "$basket" "$ROOT/README.md"; then
    echo "Missing basket in README: $basket" >&2
    exit 1
  fi
done

PRIVATE_TERM_PATTERN='[Pp][Rr][Ii][Mm][Ee]|[Tt][Hh][Ee][Aa][Ll][Ii]2x|[Ss][Ee][Nn][Tt][Ii][Nn][Ee][Ll]2x|/Users/[Nn][Oo][Dd][Ee]|[Aa][Ll][Ii][Kk][Bb]|[Bb][Ll][Oo][Ff][Ii][Nn]|[Rr][Aa][Yy][Aa][Dd]|[Ee][Ll][Dd][Aa][Rr]'
if grep -RInE "$PRIVATE_TERM_PATTERN" \
  "$ROOT" \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude='validate.sh' >/tmp/captureos_validate.$$ 2>/dev/null; then
  echo "Private or project-specific terms found:" >&2
  cat /tmp/captureos_validate.$$ >&2
  rm -f /tmp/captureos_validate.$$
  exit 1
fi
rm -f /tmp/captureos_validate.$$

echo "CaptureOS validation passed."
