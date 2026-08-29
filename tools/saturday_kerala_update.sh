#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -ne 1 ]]; then
  echo "Usage: bash tools/saturday_kerala_update.sh CONFIG_PATH"
  exit 2
fi

CONFIG="$1"
if [[ ! -f "$CONFIG" ]]; then
  echo "❌ Export configuration not found: $CONFIG"
  exit 1
fi

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

REPOSITORY_EXPORT="$(python - "$CONFIG" "$ROOT" <<'PY'
import json
from pathlib import Path
import sys

config_path = Path(sys.argv[1]).expanduser().resolve()
repository_root = Path(sys.argv[2]).resolve()
payload = json.loads(config_path.read_text(encoding='utf-8'))
value = str(payload.get('repository_export_path') or '').strip()
if not value:
    raise SystemExit('repository_export_path is missing from configuration')
path = Path(value).expanduser()
resolved = path if path.is_absolute() else repository_root / path
try:
    print(resolved.relative_to(repository_root))
except ValueError as exc:
    raise SystemExit('repository_export_path must resolve inside the repository') from exc
PY
)"

printf '%s\n' "=== SATURDAY KERALA GOVERNMENT UPDATE ==="
printf '%s\n' "Branch: $BRANCH"
printf '%s\n' "Config: $CONFIG"

# Bring the branch current before collecting anything new.
git pull --ff-only origin "$BRANCH"

# Refresh the living Government frontier and regenerate configured exports.
python tools/update_kerala_government.py --config "$CONFIG"

if [[ ! -f "$REPOSITORY_EXPORT" ]]; then
  echo "❌ Expected repository export was not created: $REPOSITORY_EXPORT"
  exit 1
fi

git add "$REPOSITORY_EXPORT"

if git diff --cached --quiet -- "$REPOSITORY_EXPORT"; then
  echo "✅ Government export unchanged; no commit required."
else
  CUTOFF="$(python - "$REPOSITORY_EXPORT" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding='utf-8'))
print(data.get('cutoff_date') or 'unknown')
PY
)"
  git commit -m "Update Kerala Government export through ${CUTOFF}"
fi

# Push even when no new commit was needed, so the remote state is explicitly synchronized.
git push origin "$BRANCH"

printf '%s\n' "=== SATURDAY UPDATE COMPLETE ==="
printf '%s\n' "GitHub-visible export: $REPOSITORY_EXPORT"
printf '%s\n' "Remote branch: origin/$BRANCH"
