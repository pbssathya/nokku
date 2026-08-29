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


SCHEMA_VERSION = 3
DRAW_DATE_FORMAT = "%d/%m/%Y"


@dataclass(frozen=True, slots=True)
class ExportConfig:
    runtime_export_directory: Path
    repository_export_directory: Path
    manifest_filename: str


def _resolve_configured_path(value: object, *, repository_root: Path) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Configured export path must not be empty")
    path = Path(text).expanduser()
    return path if path.is_absolute() else repository_root / path


def load_export_config(config_path: str | Path) -> ExportConfig:
    """Load operational export locations from an explicit configuration file."""
    target = Path(config_path).expanduser().resolve()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Export configuration must be a JSON object")

    repository_root = Path(__file__).resolve().parents[1]
    manifest_filename = str(payload.get("manifest_filename") or "").strip()
    if not manifest_filename:
        raise ValueError("manifest_filename is required")
    if Path(manifest_filename).name != manifest_filename:
        raise ValueError("manifest_filename must be a file name, not a path")

    return ExportConfig(
        runtime_export_directory=_resolve_configured_path(
            payload.get("runtime_export_directory"), repository_root=repository_root
        ),
        repository_export_directory=_resolve_configured_path(
            payload.get("repository_export_directory"), repository_root=repository_root
        ),
        manifest_filename=manifest_filename,
    )


def _parse_draw_date(value: object) -> date | None:
    try:
        return datetime.strptime(str(value or ""), DRAW_DATE_FORMAT).date()
    except ValueError:
        return None


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
            draw_date = _parse_draw_date(parsed.get("draw_date"))
            if draw_date is None or draw_date > anchor:
                continue

            known[source] = {
                "source": source,
                "draw_date": parsed.get("draw_date"),
                "lottery_name": parsed.get("lottery_name"),
                "parsed": parsed,
            }

    def sort_key(item: dict[str, object]) -> tuple[date, int, str]:
        source = str(item["source"])
        source_number = int(source) if source.isdigit() else 10**18
        draw_date = _parse_draw_date(item["draw_date"])
        assert draw_date is not None
        return draw_date, source_number, source

    return sorted(known.values(), key=sort_key)


def _iso_draw_date(record: dict[str, object] | None) -> str | None:
    if record is None:
        return None
    parsed = _parse_draw_date(record.get("draw_date"))
    return parsed.isoformat() if parsed is not None else None


def _same_content(existing: dict[str, object], candidate: dict[str, object]) -> bool:
    existing_copy = dict(existing)
    candidate_copy = dict(candidate)
    existing_copy.pop("generated_at", None)
    candidate_copy.pop("generated_at", None)
    return existing_copy == candidate_copy


def _preserve_generated_at(target: Path, candidate: dict[str, object]) -> dict[str, object]:
    if not target.exists():
        return candidate
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return candidate
    if isinstance(existing, dict) and _same_content(existing, candidate):
        candidate = dict(candidate)
        candidate["generated_at"] = existing.get("generated_at", candidate["generated_at"])
    return candidate


def _write_json(target: Path, payload: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _group_records_by_year(records: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for record in records:
        draw_date = _parse_draw_date(record.get("draw_date"))
        if draw_date is None:
            continue
        grouped.setdefault(draw_date.year, []).append(record)
    return grouped


def _shard_payload(*, year: int, records: list[dict[str, object]]) -> dict[str, object]:
    oldest = records[0] if records else None
    latest = records[-1] if records else None
    return {
        "schema_version": SCHEMA_VERSION,
        "domain_path": DOMAIN,
        "year": year,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "oldest_source": str(oldest["source"]) if oldest is not None else None,
        "oldest_draw_date": _iso_draw_date(oldest),
        "latest_source": str(latest["source"]) if latest is not None else None,
        "latest_draw_date": _iso_draw_date(latest),
        "records": records,
    }


def _manifest_payload(
    *,
    anchor: date,
    records: list[dict[str, object]],
    shards: list[dict[str, object]],
) -> dict[str, object]:
    oldest = records[0] if records else None
    latest = records[-1] if records else None
    return {
        "schema_version": SCHEMA_VERSION,
        "domain_path": DOMAIN,
        "cutoff_date": anchor.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "oldest_source": str(oldest["source"]) if oldest is not None else None,
        "oldest_draw_date": _iso_draw_date(oldest),
        "latest_source": str(latest["source"]) if latest is not None else None,
        "latest_draw_date": _iso_draw_date(latest),
        "shards": shards,
    }


def _write_sharded_export(
    *,
    target_directory: Path,
    manifest_filename: str,
    anchor: date,
    records: list[dict[str, object]],
) -> tuple[Path, list[Path]]:
    grouped = _group_records_by_year(records)
    written_shards: list[Path] = []
    manifest_shards: list[dict[str, object]] = []

    for year in sorted(grouped):
        year_records = grouped[year]
        shard_filename = f"{year}.json"
        shard_target = target_directory / shard_filename
        payload = _preserve_generated_at(
            shard_target,
            _shard_payload(year=year, records=year_records),
        )
        _write_json(shard_target, payload)
        written_shards.append(shard_target)
        manifest_shards.append(
            {
                "year": year,
                "file": shard_filename,
                "record_count": payload["record_count"],
                "oldest_source": payload["oldest_source"],
                "oldest_draw_date": payload["oldest_draw_date"],
                "latest_source": payload["latest_source"],
                "latest_draw_date": payload["latest_draw_date"],
            }
        )

    manifest_target = target_directory / manifest_filename
    manifest = _preserve_generated_at(
        manifest_target,
        _manifest_payload(anchor=anchor, records=records, shards=manifest_shards),
    )
    _write_json(manifest_target, manifest)
    return manifest_target, written_shards


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

    runtime_manifest, _ = _write_sharded_export(
        target_directory=config.runtime_export_directory,
        manifest_filename=config.manifest_filename,
        anchor=anchor,
        records=records,
    )
    repository_manifest, repository_shards = _write_sharded_export(
        target_directory=config.repository_export_directory,
        manifest_filename=config.manifest_filename,
        anchor=anchor,
        records=records,
    )

    manifest = json.loads(repository_manifest.read_text(encoding="utf-8"))

    print("=== KERALA GOVERNMENT DATA UPDATE ===")
    print("Update through:", anchor)
    print("Before:", before_latest)
    print("New sources:", refreshed or "NONE")
    print("After:", after_latest)
    print("Total verified facts:", len(after))
    print()
    print("=== BANYAN GOVERNMENT EXPORT ===")
    print("Schema version:", manifest["schema_version"])
    print("Oldest source:", manifest["oldest_source"])
    print("Oldest draw date:", manifest["oldest_draw_date"])
    print("Latest source:", manifest["latest_source"])
    print("Latest draw date:", manifest["latest_draw_date"])
    print("Records exported:", manifest["record_count"])
    print("Shard count:", len(repository_shards))
    print("Runtime manifest:", runtime_manifest)
    print("Repository manifest:", repository_manifest)
    print("Manifest bytes:", repository_manifest.stat().st_size)
    print("Largest shard bytes:", max((p.stat().st_size for p in repository_shards), default=0))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh Kerala Government lottery evidence and regenerate configured sharded exports."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to JSON configuration containing export directories and manifest filename.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(args.config)
