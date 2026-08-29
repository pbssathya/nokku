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

readarray -t EXPORT_INFO < <(python - "$CONFIG" "$ROOT" <<'PY'
import json
from pathlib import Path
import sys

config_path = Path(sys.argv[1]).expanduser().resolve()
repository_root = Path(sys.argv[2]).resolve()
payload = json.loads(config_path.read_text(encoding='utf-8'))

directory_value = str(payload.get('repository_export_directory') or '').strip()
manifest_filename = str(payload.get('manifest_filename') or '').strip()
if not directory_value:
    raise SystemExit('repository_export_directory is missing from configuration')
if not manifest_filename:
    raise SystemExit('manifest_filename is missing from configuration')

path = Path(directory_value).expanduser()
resolved = path if path.is_absolute() else repository_root / path
try:
    relative_directory = resolved.relative_to(repository_root)
except ValueError as exc:
    raise SystemExit('repository_export_directory must resolve inside the repository') from exc

print(relative_directory)
print(relative_directory / manifest_filename)
PY
)

REPOSITORY_EXPORT_DIRECTORY="${EXPORT_INFO[0]}"
REPOSITORY_MANIFEST="${EXPORT_INFO[1]}"
RECEIPT="$(mktemp)"
trap 'rm -f "$RECEIPT"' EXIT

printf '%s\n' "=== SATURDAY KERALA GOVERNMENT UPDATE ==="
printf '%s\n' "Branch: $BRANCH"
printf '%s\n' "Config: $CONFIG"

# Synchronize the branch before the lower export layer observes local state.
git pull --ff-only origin "$BRANCH"

# Lower layer: report reality through a structured receipt. It does not choose recovery.
python tools/update_kerala_government.py --config "$CONFIG" --receipt "$RECEIPT"

readarray -t RECEIPT_INFO < <(python - "$RECEIPT" <<'PY'
import json
from pathlib import Path
import sys

receipt = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(receipt.get('status') or 'unknown')
print(receipt.get('mode') or 'unknown')
print(receipt.get('manifest_state_before') or 'unknown')
print('yes' if receipt.get('manifest_changed') else 'no')
PY
)

STATUS="${RECEIPT_INFO[0]}"
MODE="${RECEIPT_INFO[1]}"
MANIFEST_STATE="${RECEIPT_INFO[2]}"
MANIFEST_CHANGED="${RECEIPT_INFO[3]}"

printf '%s\n' "=== SATURDAY ORCHESTRATION RECEIPT ==="
printf '%s\n' "Lower-layer status: $STATUS"
printf '%s\n' "Mode: $MODE"
printf '%s\n' "Manifest state before: $MANIFEST_STATE"
printf '%s\n' "Manifest changed: $MANIFEST_CHANGED"

# Upper layer policy: an unresolved lower-layer condition is surfaced, not repaired silently.
if [[ "$STATUS" != "success" ]]; then
  echo "⚠️ Saturday orchestration stopped before Git commit/push."
  echo "The lower-layer receipt requires an explicit upper-layer decision."
  python -m json.tool "$RECEIPT"
  exit 3
fi

if [[ ! -f "$REPOSITORY_MANIFEST" ]]; then
  echo "❌ Successful receipt but repository manifest is missing: $REPOSITORY_MANIFEST"
  exit 1
fi

git add -A "$REPOSITORY_EXPORT_DIRECTORY"

if git diff --cached --quiet -- "$REPOSITORY_EXPORT_DIRECTORY"; then
  echo "✅ Government export unchanged; no commit required."
else
  CUTOFF="$(python - "$REPOSITORY_MANIFEST" <<'PY'
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

# Push after a successful receipt; this also confirms remote synchronization on no-op runs.
git push origin "$BRANCH"

printf '%s\n' "=== SATURDAY UPDATE COMPLETE ==="
printf '%s\n' "Mode: $MODE"
printf '%s\n' "GitHub-visible manifest: $REPOSITORY_MANIFEST"
printf '%s\n' "Export directory: $REPOSITORY_EXPORT_DIRECTORY"
printf '%s\n' "Remote branch: origin/$BRANCH"
