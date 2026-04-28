#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/install.sh [--vault PATH]

Installs CaptureOS Hermes skills. If --vault is provided, also installs Markdown templates.

Options:
  --vault PATH   Markdown vault/folder where templates should be copied
  -h, --help     Show this help

Environment:
  HERMES_HOME    Override Hermes home directory. Defaults to ~/.hermes
EOF
}

VAULT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault)
      VAULT="${2:-}"
      if [[ -z "$VAULT" ]]; then
        echo "Missing value for --vault" >&2
        exit 1
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILL_DIR="$HERMES_HOME/skills/note-taking"

mkdir -p "$SKILL_DIR"
rm -rf "$SKILL_DIR/capture" "$SKILL_DIR/normal" "$SKILL_DIR/captureos"
cp -R "$ROOT/skills/capture" "$SKILL_DIR/capture"
cp -R "$ROOT/skills/normal" "$SKILL_DIR/normal"
cp -R "$ROOT/skills/captureos" "$SKILL_DIR/captureos"

echo "Installed CaptureOS skills into $SKILL_DIR"

if [[ -n "$VAULT" ]]; then
  VAULT="${VAULT/#\~/$HOME}"
  mkdir -p "$VAULT/wiki"
  cp "$ROOT/templates/capture-tasks-reminders.md" "$VAULT/wiki/capture-tasks-reminders.md"
  cp "$ROOT/templates/capture-events-meetings.md" "$VAULT/wiki/capture-events-meetings.md"
  cp "$ROOT/templates/capture-ideas-notes.md" "$VAULT/wiki/capture-ideas-notes.md"
  cp "$ROOT/templates/captureos-layer.md" "$VAULT/wiki/captureos-layer.md"
  cp "$ROOT/templates/CUSTOM_COMMANDS.md" "$VAULT/CUSTOM_COMMANDS.md"
  echo "Installed CaptureOS templates into $VAULT"
else
  echo "No --vault provided; skipped Markdown templates."
fi

echo "Done. Restart Hermes or its gateway if command menus need refresh."
