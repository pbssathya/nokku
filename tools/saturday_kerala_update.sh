#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="$(git branch --show-current)"
if [[ -z "$BRANCH" ]]; then
  echo "❌ Cannot update from a detached HEAD."
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "❌ Tracked working-tree changes exist. Commit/stash them before the Saturday update."
  git status --short
  exit 1
fi

printf '%s\n' "=== SATURDAY KERALA GOVERNMENT UPDATE ==="
printf '%s\n' "Branch: $BRANCH"

# Bring the branch current before collecting anything new.
git pull --ff-only origin "$BRANCH"

# Refresh the living Government frontier and regenerate both Banyan exports.
python tools/update_kerala_government.py

EXPORT="exports/kerala_lottery_government.json"
if [[ ! -f "$EXPORT" ]]; then
  echo "❌ Expected repository export was not created: $EXPORT"
  exit 1
fi

git add "$EXPORT"

if git diff --cached --quiet -- "$EXPORT"; then
  echo "✅ Government export unchanged; no commit required."
else
  CUTOFF="$(python - <<'PY'
import json
from pathlib import Path
p = Path('exports/kerala_lottery_government.json')
data = json.loads(p.read_text(encoding='utf-8'))
print(data.get('cutoff_date') or 'unknown')
PY
)"
  git commit -m "Update Kerala Government export through ${CUTOFF}"
fi

# Push even when no new commit was needed, so the remote state is explicitly synchronized.
git push origin "$BRANCH"

printf '%s\n' "=== SATURDAY UPDATE COMPLETE ==="
printf '%s\n' "GitHub-visible export: $EXPORT"
printf '%s\n' "Remote branch: origin/$BRANCH"
