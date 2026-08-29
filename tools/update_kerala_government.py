from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path

from nokku.lottery.kerala.decision import KeralaLotteryFact
from nokku.lottery.kerala.government_record_recall import (
    GovernmentRecordRecallResult,
    recall_government_records_result,
)
from nokku.lottery.kerala.living import (
    DOMAIN,
    FrontierRefreshResult,
    kerala_today,
    refresh_current_frontier_result,
)
from nokku.runtime import living_memory_path


SCHEMA_VERSION = 4
RECEIPT_VERSION = 1
DRAW_DATE_FORMAT = "%d/%m/%Y"


@dataclass(frozen=True, slots=True)
class ExportConfig:
    runtime_export_directory: Path
    repository_export_directory: Path
    manifest_filename: str
    shard_period_format: str
    shard_filename_template: str
    frontier_max_new_sources: int


def _resolve_configured_path(value: object, *, repository_root: Path) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Configured export path must not be empty")
    path = Path(text).expanduser()
    return path if path.is_absolute() else repository_root / path


def load_export_config(config_path: str | Path) -> ExportConfig:
    target = Path(config_path).expanduser().resolve()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Export configuration must be a JSON object")

    repository_root = Path(__file__).resolve().parents[1]
    manifest_filename = str(payload.get("manifest_filename") or "").strip()
    if not manifest_filename or Path(manifest_filename).name != manifest_filename:
        raise ValueError("manifest_filename must be a file name")
    shard_period_format = str(payload.get("shard_period_format") or "").strip()
    if not shard_period_format:
        raise ValueError("shard_period_format is required")
    shard_filename_template = str(payload.get("shard_filename_template") or "").strip()
    if not shard_filename_template or "{period}" not in shard_filename_template:
        raise ValueError("shard_filename_template must contain {period}")
    sample_name = shard_filename_template.format(period="sample")
    if Path(sample_name).name != sample_name:
        raise ValueError("shard_filename_template must produce a file name")
    frontier_max_new_sources = int(payload.get("frontier_max_new_sources") or 0)
    if frontier_max_new_sources < 1:
        raise ValueError("frontier_max_new_sources must be a positive integer")

    return ExportConfig(
        runtime_export_directory=_resolve_configured_path(
            payload.get("runtime_export_directory"), repository_root=repository_root
        ),
        repository_export_directory=_resolve_configured_path(
            payload.get("repository_export_directory"), repository_root=repository_root
        ),
        manifest_filename=manifest_filename,
        shard_period_format=shard_period_format,
        shard_filename_template=shard_filename_template,
        frontier_max_new_sources=frontier_max_new_sources,
    )


def _parse_draw_date(value: object) -> date | None:
    try:
        return datetime.strptime(str(value or ""), DRAW_DATE_FORMAT).date()
    except ValueError:
        return None


def _parse_iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _source_sort_key(source: str) -> tuple[int, int | str]:
    return (0, int(source)) if source.isdigit() else (1, source)


def _record_sort_key(record: dict[str, object]) -> tuple[date, tuple[int, int | str]]:
    draw_date = _parse_draw_date(record.get("draw_date"))
    if draw_date is None:
        raise ValueError("Record contains an invalid draw date")
    return draw_date, _source_sort_key(str(record.get("source") or ""))


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


def _serialized_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _write_json_if_changed(target: Path, payload: dict[str, object]) -> bool:
    serialized = _serialized_json(payload)
    if target.exists():
        try:
            if target.read_text(encoding="utf-8") == serialized:
                return False
        except OSError:
            pass
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialized, encoding="utf-8")
    return True


def _write_receipt(target: Path, payload: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_serialized_json(payload), encoding="utf-8")


def export_records(
    *,
    anchor: date,
    memory_path: Path,
    min_numeric_source_exclusive: int | None = None,
) -> list[dict[str, object]]:
    """Compatibility view returning records from the truthful recall receipt."""
    result = recall_government_records_result(
        anchor=anchor,
        memory_path=memory_path,
        min_numeric_source_exclusive=min_numeric_source_exclusive,
    )
    return list(result.records)


def _period_for_record(record: dict[str, object], *, period_format: str) -> str:
    draw_date = _parse_draw_date(record.get("draw_date"))
    if draw_date is None:
        raise ValueError("Cannot derive shard period from an invalid draw date")
    period = draw_date.strftime(period_format).strip()
    if not period:
        raise ValueError("Configured shard_period_format produced an empty period")
    return period


def _group_records_by_period(records: list[dict[str, object]], *, period_format: str) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for record in records:
        grouped.setdefault(_period_for_record(record, period_format=period_format), []).append(record)
    return grouped


def _iso_draw_date(record: dict[str, object] | None) -> str | None:
    if record is None:
        return None
    parsed = _parse_draw_date(record.get("draw_date"))
    return parsed.isoformat() if parsed is not None else None


def _shard_payload(*, period: str, records: list[dict[str, object]]) -> dict[str, object]:
    oldest = records[0] if records else None
    latest = records[-1] if records else None
    return {
        "schema_version": SCHEMA_VERSION,
        "domain_path": DOMAIN,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "oldest_source": str(oldest["source"]) if oldest is not None else None,
        "oldest_draw_date": _iso_draw_date(oldest),
        "latest_source": str(latest["source"]) if latest is not None else None,
        "latest_draw_date": _iso_draw_date(latest),
        "records": records,
    }


def _manifest_payload(*, anchor: date, shards: list[dict[str, object]], config: ExportConfig) -> dict[str, object]:
    ordered = sorted(shards, key=lambda item: _parse_iso_date(item.get("oldest_draw_date")) or date.max)
    oldest = ordered[0] if ordered else None
    latest = max(ordered, key=lambda item: _parse_iso_date(item.get("latest_draw_date")) or date.min, default=None)
    return {
        "schema_version": SCHEMA_VERSION,
        "domain_path": DOMAIN,
        "cutoff_date": anchor.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": sum(int(item["record_count"]) for item in ordered),
        "oldest_source": oldest.get("oldest_source") if oldest else None,
        "oldest_draw_date": oldest.get("oldest_draw_date") if oldest else None,
        "latest_source": latest.get("latest_source") if latest else None,
        "latest_draw_date": latest.get("latest_draw_date") if latest else None,
        "shard_period_format": config.shard_period_format,
        "shard_filename_template": config.shard_filename_template,
        "shards": ordered,
    }


def _manifest_path(config: ExportConfig) -> Path:
    return config.repository_export_directory / config.manifest_filename


def _inspect_manifest(config: ExportConfig) -> tuple[str, dict[str, object] | None, list[str]]:
    target = _manifest_path(config)
    if not target.exists():
        return "missing", None, []
    errors: list[str] = []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return "invalid", None, [f"manifest_read_error:{exc}"]
    if not isinstance(payload, dict):
        return "invalid", None, ["manifest_not_object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    if payload.get("domain_path") != DOMAIN:
        errors.append("domain_path_mismatch")
    if payload.get("shard_period_format") != config.shard_period_format:
        errors.append("shard_period_format_mismatch")
    if payload.get("shard_filename_template") != config.shard_filename_template:
        errors.append("shard_filename_template_mismatch")
    latest_source = str(payload.get("latest_source") or "")
    latest_date = _parse_iso_date(payload.get("latest_draw_date"))
    if not latest_source or not latest_source.isdigit():
        errors.append("latest_source_not_numeric")
    if latest_date is None:
        errors.append("latest_draw_date_invalid")
    shards = payload.get("shards")
    if not isinstance(shards, list) or not shards:
        errors.append("shards_missing_or_empty")
        shards = []
    filenames: set[str] = set()
    latest_record_found = False
    for item in shards:
        if not isinstance(item, dict):
            errors.append("invalid_shard_manifest_entry")
            continue
        filename = str(item.get("file") or "")
        if not filename or Path(filename).name != filename:
            errors.append("invalid_shard_filename")
            continue
        if filename in filenames:
            errors.append(f"duplicate_shard_filename:{filename}")
        filenames.add(filename)
        shard_path = config.repository_export_directory / filename
        if not shard_path.exists():
            errors.append(f"missing_shard:{filename}")
            continue
        if str(item.get("latest_source") or "") == latest_source and _parse_iso_date(item.get("latest_draw_date")) == latest_date:
            try:
                shard = json.loads(shard_path.read_text(encoding="utf-8"))
                records = shard.get("records") if isinstance(shard, dict) else None
                if isinstance(records, list):
                    latest_record_found = any(
                        isinstance(record, dict)
                        and str(record.get("source") or "") == latest_source
                        and _parse_draw_date(record.get("draw_date")) == latest_date
                        for record in records
                    )
            except (json.JSONDecodeError, OSError):
                errors.append(f"latest_shard_unreadable:{filename}")
    if not latest_record_found:
        errors.append("latest_record_not_found_in_declared_shards")
    expected_count = sum(int(item.get("record_count") or 0) for item in shards if isinstance(item, dict))
    if int(payload.get("record_count") or -1) != expected_count:
        errors.append("record_count_mismatch")
    return ("invalid" if errors else "valid"), payload, errors


def _frontier_fact_from_manifest(manifest: dict[str, object], *, repository_export_directory: Path) -> KeralaLotteryFact:
    latest_source = str(manifest["latest_source"])
    latest_date = _parse_iso_date(manifest["latest_draw_date"])
    if latest_date is None:
        raise ValueError("Manifest latest_draw_date is invalid")
    for item in manifest["shards"]:
        if not isinstance(item, dict):
            continue
        if str(item.get("latest_source") or "") != latest_source or _parse_iso_date(item.get("latest_draw_date")) != latest_date:
            continue
        payload = json.loads((repository_export_directory / str(item["file"])).read_text(encoding="utf-8"))
        for record in payload.get("records", []):
            if str(record.get("source") or "") == latest_source and _parse_draw_date(record.get("draw_date")) == latest_date:
                return KeralaLotteryFact(source=latest_source, draw_date=latest_date, lottery_name=str(record.get("lottery_name") or ""))
    raise ValueError("Manifest checkpoint record could not be loaded")


def _latest_numeric_fact(records: list[dict[str, object]]) -> KeralaLotteryFact | None:
    numeric = [record for record in records if str(record.get("source") or "").isdigit()]
    if not numeric:
        return None
    record = max(numeric, key=lambda item: int(str(item["source"])))
    draw_date = _parse_draw_date(record.get("draw_date"))
    if draw_date is None:
        return None
    return KeralaLotteryFact(source=str(record["source"]), draw_date=draw_date, lottery_name=str(record.get("lottery_name") or ""))


def _remove_stale_shards(*, target_directory: Path, expected_filenames: set[str], manifest_filename: str) -> list[Path]:
    removed: list[Path] = []
    if not target_directory.exists():
        return removed
    protected = set(expected_filenames)
    protected.add(manifest_filename)
    for path in target_directory.iterdir():
        if path.is_file() and path.name not in protected and path.suffix.lower() == ".json":
            path.unlink()
            removed.append(path)
    return removed


def _write_bootstrap_export(*, target_directory: Path, config: ExportConfig, anchor: date, records: list[dict[str, object]]) -> tuple[Path, list[Path], list[Path], list[Path], bool]:
    grouped = _group_records_by_period(records, period_format=config.shard_period_format)
    all_shards: list[Path] = []
    changed_shards: list[Path] = []
    manifest_shards: list[dict[str, object]] = []
    expected_filenames: set[str] = set()
    for period, period_records in sorted(grouped.items(), key=lambda item: _record_sort_key(item[1][0])):
        filename = config.shard_filename_template.format(period=period)
        expected_filenames.add(filename)
        target = target_directory / filename
        payload = _preserve_generated_at(target, _shard_payload(period=period, records=period_records))
        if _write_json_if_changed(target, payload):
            changed_shards.append(target)
        all_shards.append(target)
        manifest_shards.append({
            "period": period,
            "file": filename,
            "record_count": payload["record_count"],
            "oldest_source": payload["oldest_source"],
            "oldest_draw_date": payload["oldest_draw_date"],
            "latest_source": payload["latest_source"],
            "latest_draw_date": payload["latest_draw_date"],
        })
    removed = _remove_stale_shards(target_directory=target_directory, expected_filenames=expected_filenames, manifest_filename=config.manifest_filename)
    manifest_target = target_directory / config.manifest_filename
    manifest = _preserve_generated_at(manifest_target, _manifest_payload(anchor=anchor, shards=manifest_shards, config=config))
    manifest_changed = _write_json_if_changed(manifest_target, manifest)
    return manifest_target, all_shards, changed_shards, removed, manifest_changed


def _read_shard_records(target: Path) -> list[dict[str, object]]:
    payload = json.loads(target.read_text(encoding="utf-8"))
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise ValueError(f"Shard has no records array: {target}")
    return [record for record in records if isinstance(record, dict)]


def _incremental_export(*, config: ExportConfig, manifest: dict[str, object], anchor: date, new_records: list[dict[str, object]]) -> tuple[dict[str, object], list[str], int, int, bool]:
    shard_entries = [dict(item) for item in manifest.get("shards", []) if isinstance(item, dict)]
    by_period = {str(item["period"]): item for item in shard_entries}
    changed_files: list[str] = []
    records_added = 0
    records_updated = 0
    grouped = _group_records_by_period(new_records, period_format=config.shard_period_format)
    for period, additions in grouped.items():
        filename = config.shard_filename_template.format(period=period)
        repo_target = config.repository_export_directory / filename
        existing_records = _read_shard_records(repo_target) if repo_target.exists() else []
        known = {str(record.get("source") or ""): record for record in existing_records}
        for record in additions:
            source = str(record["source"])
            if source in known:
                if known[source] != record:
                    records_updated += 1
            else:
                records_added += 1
            known[source] = record
        merged = sorted(known.values(), key=_record_sort_key)
        payload = _preserve_generated_at(repo_target, _shard_payload(period=period, records=merged))
        repo_changed = _write_json_if_changed(repo_target, payload)
        _write_json_if_changed(config.runtime_export_directory / filename, payload)
        if repo_changed:
            changed_files.append(filename)
        by_period[period] = {
            "period": period,
            "file": filename,
            "record_count": payload["record_count"],
            "oldest_source": payload["oldest_source"],
            "oldest_draw_date": payload["oldest_draw_date"],
            "latest_source": payload["latest_source"],
            "latest_draw_date": payload["latest_draw_date"],
        }
    new_manifest = _manifest_payload(anchor=anchor, shards=list(by_period.values()), config=config)
    repo_manifest_target = _manifest_path(config)
    new_manifest = _preserve_generated_at(repo_manifest_target, new_manifest)
    manifest_changed = _write_json_if_changed(repo_manifest_target, new_manifest)
    _write_json_if_changed(config.runtime_export_directory / config.manifest_filename, new_manifest)
    return new_manifest, changed_files, records_added, records_updated, manifest_changed


def _government_record_recall_payload(
    result: GovernmentRecordRecallResult,
) -> dict[str, object]:
    memory = result.memory_discovery
    return {
        "status": result.status,
        "record_count": len(result.records),
        "examined_values": result.examined_values,
        "matching_collection_values": result.matching_collection_values,
        "usable_matching_values": result.usable_matching_values,
        "filtered_by_checkpoint": result.filtered_by_checkpoint,
        "filtered_after_anchor": result.filtered_after_anchor,
        "failures": list(result.failures),
        "uncertainty": list(result.uncertainty),
        "memory_discovery": {
            "status": memory.status,
            "discovered_receipt_count": memory.discovered_receipt_count,
            "attempted_memory_ids": list(memory.attempted_memory_ids),
            "discovery_disposition_status": memory.discovery_disposition_status,
            "failures": list(memory.failures),
            "uncertainty": list(memory.uncertainty),
        },
    }


def _apply_government_record_recall(
    receipt: dict[str, object],
    result: GovernmentRecordRecallResult,
) -> bool:
    """Transfer one Government-record recall receipt to export orchestration."""
    raw_attempts = receipt.get("government_record_recall_attempts")
    attempts = list(raw_attempts) if isinstance(raw_attempts, list) else []
    attempts.append(_government_record_recall_payload(result))
    receipt["government_record_recall_attempts"] = attempts

    failures = receipt.get("failures")
    receipt_failures = list(failures) if isinstance(failures, list) else []
    uncertainty = receipt.get("uncertainty")
    receipt_uncertainty = (
        list(uncertainty) if isinstance(uncertainty, list) else []
    )

    receipt_failures.extend(result.failures)
    receipt_uncertainty.extend(result.uncertainty)
    receipt["failures"] = receipt_failures
    receipt["uncertainty"] = receipt_uncertainty

    if result.status == "success":
        return True

    receipt["status"] = "needs_decision"
    if not result.failures and not result.uncertainty:
        receipt_uncertainty.append(
            f"government_record_recall_requires_decision:{result.status}"
        )
    return False


def _frontier_refresh_payload(
    result: FrontierRefreshResult | None,
) -> dict[str, object]:
    if result is None:
        return {"status": "not_requested"}
    return {
        "status": result.status,
        "refreshed_sources": list(result.refreshed_sources),
        "attempted_sources": list(result.attempted_sources),
        "checkpoint_source": result.checkpoint_source,
        "checkpoint_draw_date": (
            result.checkpoint_draw_date.isoformat()
            if result.checkpoint_draw_date is not None
            else None
        ),
        "stop_reason": result.stop_reason,
        "preservation_attempts": [
            {
                "status": attempt.status,
                "memory_id": attempt.memory_id,
                "disposition_status": attempt.disposition_status,
                "feedback_count": attempt.feedback_count,
                "memory_event": attempt.memory_event,
                "stored_at": (
                    attempt.stored_at.isoformat()
                    if hasattr(attempt.stored_at, "isoformat")
                    else attempt.stored_at
                ),
                "sha256": attempt.sha256,
                "failures": list(attempt.failures),
                "uncertainty": list(attempt.uncertainty),
            }
            for attempt in result.preservation_attempts
        ],
        "failures": list(result.failures),
        "uncertainty": list(result.uncertainty),
    }


def _apply_frontier_result(
    receipt: dict[str, object],
    result: FrontierRefreshResult,
) -> bool:
    """Transfer the frontier receipt and say whether export may continue."""
    receipt["frontier_refresh"] = _frontier_refresh_payload(result)
    receipt["collector_sources_added"] = list(result.refreshed_sources)

    failures = receipt.get("failures")
    receipt_failures = list(failures) if isinstance(failures, list) else []
    uncertainty = receipt.get("uncertainty")
    receipt_uncertainty = (
        list(uncertainty) if isinstance(uncertainty, list) else []
    )

    receipt_failures.extend(result.failures)
    receipt_uncertainty.extend(result.uncertainty)
    receipt["failures"] = receipt_failures
    receipt["uncertainty"] = receipt_uncertainty

    if result.status in ("success", "current"):
        return True

    receipt["status"] = "needs_decision"
    if not result.failures and not result.uncertainty:
        receipt_uncertainty.append(
            f"frontier_refresh_requires_decision:"
            f"{result.status}:{result.stop_reason}"
        )
    return False


def _receipt_base(*, anchor: date, manifest_state: str) -> dict[str, object]:
    return {
        "receipt_version": RECEIPT_VERSION,
        "layer": "kerala_government_export",
        "status": "success",
        "mode": None,
        "anchor_date": anchor.isoformat(),
        "manifest_state_before": manifest_state,
        "checkpoint_before": None,
        "government_record_recall_attempts": [],
        "memory_sources_found_after_checkpoint": [],
        "frontier_refresh": {"status": "not_requested"},
        "collector_sources_added": [],
        "records_added": 0,
        "records_updated": 0,
        "changed_repository_shards": [],
        "removed_repository_shards": [],
        "manifest_changed": False,
        "checkpoint_after": None,
        "failures": [],
        "uncertainty": [],
    }


def _print_receipt_summary(receipt: dict[str, object]) -> None:
    print()
    print("=== EXPORT LAYER RECEIPT ===")
    print("Status:", receipt["status"])
    print("Mode:", receipt["mode"])
    print("Manifest state before:", receipt["manifest_state_before"])
    print("Checkpoint before:", receipt["checkpoint_before"])
    print(
        "Government record recall attempts:",
        receipt["government_record_recall_attempts"],
    )
    print("Memory sources after checkpoint:", receipt["memory_sources_found_after_checkpoint"])
    print("Frontier refresh:", receipt["frontier_refresh"])
    print("Collector sources added:", receipt["collector_sources_added"])
    print("Records added:", receipt["records_added"])
    print("Records updated:", receipt["records_updated"])
    print("Changed repository shards:", receipt["changed_repository_shards"])
    print("Removed repository shards:", receipt["removed_repository_shards"])
    print("Manifest changed:", "YES" if receipt["manifest_changed"] else "NO")
    print("Checkpoint after:", receipt["checkpoint_after"])
    print("Failures:", receipt["failures"] or "NONE")
    print("Uncertainty:", receipt["uncertainty"] or "NONE")


def main(config_path: str | Path, receipt_path: str | Path) -> None:
    config = load_export_config(config_path)
    anchor = kerala_today()
    memory_path = living_memory_path()
    manifest_state, manifest, manifest_errors = _inspect_manifest(config)
    receipt = _receipt_base(anchor=anchor, manifest_state=manifest_state)

    if manifest_state == "invalid":
        receipt["status"] = "needs_decision"
        receipt["mode"] = "none"
        receipt["failures"] = manifest_errors
        _write_receipt(Path(receipt_path), receipt)
        _print_receipt_summary(receipt)
        return

    if manifest_state == "missing":
        receipt["mode"] = "bootstrap"
        record_recall = recall_government_records_result(
            anchor=anchor,
            memory_path=memory_path,
        )
        if not _apply_government_record_recall(receipt, record_recall):
            _write_receipt(Path(receipt_path), receipt)
            _print_receipt_summary(receipt)
            return
        records = list(record_recall.records)
        frontier = _latest_numeric_fact(records)
        frontier_result = refresh_current_frontier_result(
            anchor=anchor,
            facts=((frontier,) if frontier is not None else ()),
            memory_path=memory_path,
            max_new_sources=config.frontier_max_new_sources,
        )
        if not _apply_frontier_result(receipt, frontier_result):
            _write_receipt(Path(receipt_path), receipt)
            _print_receipt_summary(receipt)
            return
        if frontier_result.refreshed_sources:
            record_recall = recall_government_records_result(
                anchor=anchor,
                memory_path=memory_path,
            )
            if not _apply_government_record_recall(receipt, record_recall):
                _write_receipt(Path(receipt_path), receipt)
                _print_receipt_summary(receipt)
                return
            records = list(record_recall.records)
        repo_manifest, repo_shards, changed, removed, manifest_changed = _write_bootstrap_export(
            target_directory=config.repository_export_directory,
            config=config,
            anchor=anchor,
            records=records,
        )
        _write_bootstrap_export(
            target_directory=config.runtime_export_directory,
            config=config,
            anchor=anchor,
            records=records,
        )
        final_manifest = json.loads(repo_manifest.read_text(encoding="utf-8"))
        receipt["records_added"] = int(final_manifest["record_count"])
        receipt["changed_repository_shards"] = [path.name for path in changed]
        receipt["removed_repository_shards"] = [path.name for path in removed]
        receipt["manifest_changed"] = manifest_changed
        receipt["checkpoint_after"] = {
            "source": final_manifest.get("latest_source"),
            "draw_date": final_manifest.get("latest_draw_date"),
            "record_count": final_manifest.get("record_count"),
        }
        print("=== BANYAN GOVERNMENT EXPORT ===")
        print("Mode: BOOTSTRAP")
        print("Records exported:", final_manifest["record_count"])
        print("Shard count:", len(repo_shards))
        print("Latest source:", final_manifest["latest_source"])
        print("Latest draw date:", final_manifest["latest_draw_date"])
        _write_receipt(Path(receipt_path), receipt)
        _print_receipt_summary(receipt)
        return

    assert manifest is not None
    receipt["mode"] = "incremental"
    checkpoint_source = str(manifest["latest_source"])
    checkpoint_date = _parse_iso_date(manifest["latest_draw_date"])
    assert checkpoint_date is not None
    checkpoint_number = int(checkpoint_source)
    receipt["checkpoint_before"] = {
        "source": checkpoint_source,
        "draw_date": checkpoint_date.isoformat(),
        "record_count": manifest["record_count"],
    }

    record_recall = recall_government_records_result(
        anchor=anchor,
        memory_path=memory_path,
        min_numeric_source_exclusive=checkpoint_number,
    )
    if not _apply_government_record_recall(receipt, record_recall):
        _write_receipt(Path(receipt_path), receipt)
        _print_receipt_summary(receipt)
        return
    preserved_new = list(record_recall.records)
    receipt["memory_sources_found_after_checkpoint"] = [
        str(record["source"]) for record in preserved_new
    ]
    frontier = _latest_numeric_fact(preserved_new)
    if frontier is None:
        frontier = _frontier_fact_from_manifest(manifest, repository_export_directory=config.repository_export_directory)

    frontier_result = refresh_current_frontier_result(
        anchor=anchor,
        facts=(frontier,),
        memory_path=memory_path,
        max_new_sources=config.frontier_max_new_sources,
    )
    if not _apply_frontier_result(receipt, frontier_result):
        _write_receipt(Path(receipt_path), receipt)
        _print_receipt_summary(receipt)
        return

    if frontier_result.refreshed_sources:
        record_recall = recall_government_records_result(
            anchor=anchor,
            memory_path=memory_path,
            min_numeric_source_exclusive=checkpoint_number,
        )
        if not _apply_government_record_recall(receipt, record_recall):
            _write_receipt(Path(receipt_path), receipt)
            _print_receipt_summary(receipt)
            return
        preserved_new = list(record_recall.records)
        receipt["memory_sources_found_after_checkpoint"] = [
            str(record["source"]) for record in preserved_new
        ]

    numeric_sources = sorted(int(str(record["source"])) for record in preserved_new if str(record["source"]).isdigit())
    if numeric_sources:
        expected = list(range(checkpoint_number + 1, max(numeric_sources) + 1))
        if numeric_sources != expected:
            missing = sorted(set(expected) - set(numeric_sources))
            receipt["status"] = "needs_decision"
            receipt["failures"] = [f"source_gap_after_checkpoint:{missing}"]
            _write_receipt(Path(receipt_path), receipt)
            _print_receipt_summary(receipt)
            return

    final_manifest, changed_files, added, updated, manifest_changed = _incremental_export(
        config=config,
        manifest=manifest,
        anchor=anchor,
        new_records=preserved_new,
    )
    receipt["records_added"] = added
    receipt["records_updated"] = updated
    receipt["changed_repository_shards"] = changed_files
    receipt["manifest_changed"] = manifest_changed
    receipt["checkpoint_after"] = {
        "source": final_manifest.get("latest_source"),
        "draw_date": final_manifest.get("latest_draw_date"),
        "record_count": final_manifest.get("record_count"),
    }
    print("=== BANYAN GOVERNMENT EXPORT ===")
    print("Mode: INCREMENTAL")
    print("Checkpoint source:", checkpoint_source)
    print("Checkpoint draw date:", checkpoint_date)
    print("New preserved records:", len(preserved_new))
    print("Frontier status:", frontier_result.status)
    print("Frontier stop reason:", frontier_result.stop_reason)
    print(
        "Collector sources added:",
        frontier_result.refreshed_sources or "NONE",
    )
    print("Changed repository shards:", len(changed_files))
    print("Repository manifest changed:", "YES" if manifest_changed else "NO")
    print("Latest source:", final_manifest["latest_source"])
    print("Latest draw date:", final_manifest["latest_draw_date"])
    _write_receipt(Path(receipt_path), receipt)
    _print_receipt_summary(receipt)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Government evidence using a manifest-first incremental export.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--receipt", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(args.config, args.receipt)
