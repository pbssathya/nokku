"""Truthful recall of full Kerala Government lottery collection records.

This module reuses Nokku's COSsse Memory handoff receipt and performs only the
Government-export interpretation step. It keeps the complete parsed Collector
payload required by shared evidence exports while reporting relevant-but-unusable
preserved values instead of silently dropping them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from cossse.memory import Memory

from nokku.memory_flow import MemoryDiscoveryResult, discover_preserved_values
from nokku.runtime import living_memory_path


KERALA_LOTTERY_DOMAIN = "games/chance/lottery/kerala"
DRAW_DATE_FORMAT = "%d/%m/%Y"
USABLE_COLLECTION_STATUSES = ("success", "partial")


@dataclass(frozen=True, slots=True)
class GovernmentRecordRecallResult:
    """Receipt for recalling full Government evidence records from Memory."""

    status: str
    records: tuple[dict[str, object], ...]
    memory_discovery: MemoryDiscoveryResult
    examined_values: int
    matching_collection_values: int
    usable_matching_values: int
    filtered_by_checkpoint: int
    filtered_after_anchor: int
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _parse_draw_date(value: object) -> date | None:
    try:
        return datetime.strptime(str(value or ""), DRAW_DATE_FORMAT).date()
    except ValueError:
        return None


def _source_sort_key(source: str) -> tuple[int, int | str]:
    return (0, int(source)) if source.isdigit() else (1, source)


def _record_sort_key(record: dict[str, object]) -> tuple[date, tuple[int, int | str]]:
    draw_date = _parse_draw_date(record.get("draw_date"))
    if draw_date is None:
        raise ValueError("Government record contains an invalid draw date")
    return draw_date, _source_sort_key(str(record.get("source") or ""))


def interpret_government_record_values(
    memory_discovery: MemoryDiscoveryResult,
    *,
    anchor: date,
    min_numeric_source_exclusive: int | None = None,
) -> GovernmentRecordRecallResult:
    """Interpret full Government records without hiding matching malformed evidence."""
    failures = list(memory_discovery.failures)
    uncertainty = list(memory_discovery.uncertainty)
    known: dict[str, dict[str, object]] = {}
    matching = 0
    usable = 0
    filtered_checkpoint = 0
    filtered_after_anchor = 0

    for index, value in enumerate(memory_discovery.values):
        body = value.get("body")
        if not isinstance(body, dict):
            uncertainty.append(
                f"preserved value {index} has no object body; relevance could not be classified"
            )
            continue

        if body.get("experience") != "capability_attempt":
            continue
        if body.get("capability") != "collect":
            continue

        outcome = body.get("outcome")
        if not isinstance(outcome, dict):
            uncertainty.append(
                f"collect capability value {index} has no object outcome; domain could not be classified"
            )
            continue

        request = outcome.get("request")
        if not isinstance(request, dict):
            uncertainty.append(
                f"collect capability value {index} has no object request; domain could not be classified"
            )
            continue
        if request.get("domain_path") != KERALA_LOTTERY_DOMAIN:
            continue

        matching += 1
        source = str(request.get("source") or "").strip()
        execution = outcome.get("execution")
        execution_status = (
            str(execution.get("status") or "unknown")
            if isinstance(execution, dict)
            else "unknown"
        )
        if execution_status not in USABLE_COLLECTION_STATUSES:
            uncertainty.append(
                f"Government collection evidence {source or f'at value {index}'} "
                f"has unusable execution status: {execution_status}"
            )
            continue
        if not source:
            uncertainty.append(
                f"Government collection evidence at value {index} has no source"
            )
            continue

        if min_numeric_source_exclusive is not None:
            if not source.isdigit() or int(source) <= min_numeric_source_exclusive:
                filtered_checkpoint += 1
                continue

        data = outcome.get("data")
        parsed = data.get("parsed") if isinstance(data, dict) else None
        if not isinstance(parsed, dict):
            uncertainty.append(
                f"Government collection evidence {source} has no object parsed payload"
            )
            continue

        draw_date = _parse_draw_date(parsed.get("draw_date"))
        if draw_date is None:
            uncertainty.append(
                f"Government collection evidence {source} has no usable draw date"
            )
            continue
        if draw_date > anchor:
            filtered_after_anchor += 1
            continue

        lottery_name = " ".join(str(parsed.get("lottery_name") or "").split())
        if not lottery_name or lottery_name == "Unknown":
            uncertainty.append(
                f"Government collection evidence {source} has no usable lottery name"
            )
            continue

        usable += 1
        # Discovery order is storage order; later corrections win for one source.
        known[source] = {
            "source": source,
            "draw_date": parsed.get("draw_date"),
            "lottery_name": parsed.get("lottery_name"),
            "parsed": parsed,
        }

    if memory_discovery.status == "failed":
        status = "failed"
    elif failures or uncertainty or memory_discovery.status != "success":
        status = "partial"
    else:
        status = "success"

    return GovernmentRecordRecallResult(
        status=status,
        records=tuple(sorted(known.values(), key=_record_sort_key)),
        memory_discovery=memory_discovery,
        examined_values=len(memory_discovery.values),
        matching_collection_values=matching,
        usable_matching_values=usable,
        filtered_by_checkpoint=filtered_checkpoint,
        filtered_after_anchor=filtered_after_anchor,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )


def recall_government_records_result(
    *,
    anchor: date,
    memory_path: str | Path | None = None,
    min_numeric_source_exclusive: int | None = None,
) -> GovernmentRecordRecallResult:
    """Recall full Government records and return the complete handoff receipt."""
    target = Path(memory_path) if memory_path is not None else living_memory_path()
    with Memory(target) as memory:
        discovery = discover_preserved_values(memory, requester="nokku")
    return interpret_government_record_values(
        discovery,
        anchor=anchor,
        min_numeric_source_exclusive=min_numeric_source_exclusive,
    )
