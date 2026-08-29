from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path

from cossse.memory import Memory
from nokku.lottery.kerala.living import (
    DOMAIN,
    _discover_values,
    kerala_today,
    recall_kerala_facts,
    refresh_current_frontier,
)
from nokku.runtime import living_memory_path


@dataclass(frozen=True, slots=True)
class ExportConfig:
    runtime_export_path: Path
    repository_export_path: Path


def _resolve_configured_path(value: object, *, repository_root: Path) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Configured export path must not be empty")
    path = Path(text).expanduser()
    return path if path.is_absolute() else repository_root / path


def load_export_config(config_path: str | Path) -> ExportConfig:
    """Load operational export paths from an explicit configuration file."""
    target = Path(config_path).expanduser().resolve()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Export configuration must be a JSON object")

    repository_root = Path(__file__).resolve().parents[1]
    return ExportConfig(
        runtime_export_path=_resolve_configured_path(
            payload.get("runtime_export_path"),
            repository_root=repository_root,
        ),
        repository_export_path=_resolve_configured_path(
            payload.get("repository_export_path"),
            repository_root=repository_root,
        ),
    )


def export_records(*, anchor: date, memory_path: Path) -> list[dict[str, object]]:
    """Return every usable preserved official draw report available through anchor."""
    known: dict[str, dict[str, object]] = {}

    with Memory(memory_path) as memory:
        for value in _discover_values(memory):
            body = value.get("body", {})
            if body.get("experience") != "capability_attempt":
                continue
            if body.get("capability") != "collect":
                continue

            outcome = body.get("outcome") or {}
            request = outcome.get("request") or {}
            if request.get("domain_path") != DOMAIN:
                continue

            status = (outcome.get("execution") or {}).get("status")
            if status not in ("success", "partial"):
                continue

            source = str(request.get("source") or "")
            if not source:
                continue

            parsed = (outcome.get("data") or {}).get("parsed") or {}
            raw_date = str(parsed.get("draw_date") or "")
            try:
                draw_date = datetime.strptime(raw_date, "%d/%m/%Y").date()
            except ValueError:
                continue

            if draw_date > anchor:
                continue

            # Receipt order is storage order; a later correction for one source wins.
            known[source] = {
                "source": source,
                "draw_date": raw_date,
                "lottery_name": parsed.get("lottery_name"),
                "parsed": parsed,
            }

    def sort_key(item: dict[str, object]) -> tuple[date, int, str]:
        source = str(item["source"])
        source_number = int(source) if source.isdigit() else 10**18
        return (
            datetime.strptime(str(item["draw_date"]), "%d/%m/%Y").date(),
            source_number,
            source,
        )

    return sorted(known.values(), key=sort_key)


def _same_export_content(existing: dict[str, object], candidate: dict[str, object]) -> bool:
    """Ignore generated_at so rerunning an unchanged Saturday update stays clean."""
    existing_copy = dict(existing)
    candidate_copy = dict(candidate)
    existing_copy.pop("generated_at", None)
    candidate_copy.pop("generated_at", None)
    return existing_copy == candidate_copy


def _iso_draw_date(record: dict[str, object] | None) -> str | None:
    if record is None:
        return None
    return datetime.strptime(str(record["draw_date"]), "%d/%m/%Y").date().isoformat()


def _payload_for_export(
    *,
    anchor: date,
    records: list[dict[str, object]],
    repository_export_path: Path,
) -> dict[str, object]:
    oldest = records[0] if records else None
    latest = records[-1] if records else None

    candidate = {
        "schema_version": 2,
        "domain_path": DOMAIN,
        "export_start_date": _iso_draw_date(oldest),
        "cutoff_date": anchor.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "oldest_source": str(oldest["source"]) if oldest is not None else None,
        "oldest_draw_date": _iso_draw_date(oldest),
        "latest_source": str(latest["source"]) if latest is not None else None,
        "latest_draw_date": _iso_draw_date(latest),
        "record_count": len(records),
        "records": records,
    }

    if not repository_export_path.exists():
        return candidate

    try:
        existing = json.loads(repository_export_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return candidate

    if isinstance(existing, dict) and _same_export_content(existing, candidate):
        candidate["generated_at"] = existing.get("generated_at", candidate["generated_at"])

    return candidate


def _write_export(target: Path, payload: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(config_path: str | Path) -> None:
    config = load_export_config(config_path)
    anchor = kerala_today()
    memory_path = living_memory_path()

    before = recall_kerala_facts(memory_path)
    before_latest = max(before, key=lambda item: item.draw_date) if before else None

    refreshed = refresh_current_frontier(
        anchor=anchor,
        facts=before,
        memory_path=memory_path,
    )

    after = recall_kerala_facts(memory_path)
    after_latest = max(after, key=lambda item: item.draw_date) if after else None

    records = export_records(anchor=anchor, memory_path=memory_path)
    payload = _payload_for_export(
        anchor=anchor,
        records=records,
        repository_export_path=config.repository_export_path,
    )

    _write_export(config.runtime_export_path, payload)
    _write_export(config.repository_export_path, payload)

    print("=== KERALA GOVERNMENT DATA UPDATE ===")
    print("Update through:", anchor)
    print("Before:", before_latest)
    print("New sources:", refreshed or "NONE")
    print("After:", after_latest)
    print("Total verified facts:", len(after))
    print()
    print("=== BANYAN GOVERNMENT EXPORT ===")
    print("Schema version:", payload["schema_version"])
    print("Oldest source:", payload["oldest_source"])
    print("Oldest draw date:", payload["oldest_draw_date"])
    print("Latest source:", payload["latest_source"])
    print("Latest draw date:", payload["latest_draw_date"])
    print("Records exported:", len(records))
    print("Runtime export:", config.runtime_export_path)
    print("Repository export:", config.repository_export_path)
    print("Export bytes:", config.repository_export_path.stat().st_size)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh Kerala Government lottery evidence and regenerate configured exports."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to JSON configuration containing runtime_export_path and repository_export_path.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(args.config)
