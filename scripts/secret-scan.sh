#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

patterns=(
  'gho_[A-Za-z0-9_]+'
  'ghp_[A-Za-z0-9_]+'
  'github_pat_[A-Za-z0-9_]+'
  'xox[baprs]-[A-Za-z0-9-]+'
  'bot[0-9]+:[A-Za-z0-9_-]+'
  'AIza[0-9A-Za-z_-]+'
  'sk-[A-Za-z0-9]{20,}'
  '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
  '/Users/[A-Za-z0-9._-]+'
)

status=0
for p in "${patterns[@]}"; do
  if grep -RInE --exclude-dir=.git --exclude-dir=.venv --exclude='secret-scan.sh' --exclude='validate.sh' "$p" "$ROOT" >/tmp/captureos_scan.$$ 2>/dev/null; then
    echo "Potential sensitive pattern: $p"
    cat /tmp/captureos_scan.$$
    status=1
  fi
done
rm -f /tmp/captureos_scan.$$

if [[ $status -eq 0 ]]; then
  echo "No obvious sensitive patterns found."
else
  echo "Review findings before publishing." >&2
fi
exit $status
