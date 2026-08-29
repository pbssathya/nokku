"""Truthful interpretation of preserved Kerala Lottery collection evidence.

COSsse Memory discovery/recall is handled by :mod:`nokku.memory_flow`. This
module owns only the Kerala Lottery interpretation step: decide which preserved
values are relevant facts, report relevant-but-unusable evidence, and keep
ordinary unrelated preserved values as normal filtering rather than failures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from cossse.memory import Memory

from nokku.memory_flow import MemoryDiscoveryResult, discover_preserved_values
from nokku.runtime import living_memory_path

from .decision import KeralaLotteryFact


KERALA_LOTTERY_DOMAIN = "games/chance/lottery/kerala"
DRAW_DATE_FORMAT = "%d/%m/%Y"
USABLE_COLLECTION_STATUSES = ("success", "partial")


@dataclass(frozen=True, slots=True)
class KeralaFactRecallResult:
    """Receipt for Memory handoff plus Kerala-specific fact interpretation."""

    status: str
    facts: tuple[KeralaLotteryFact, ...]
    memory_discovery: MemoryDiscoveryResult
    examined_values: int
    matching_collection_values: int
    usable_matching_values: int
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _parse_draw_date(value: object) -> date | None:
    text = str(value or "")
    if not text or text == "Unknown":
        return None
    try:
        return datetime.strptime(text, DRAW_DATE_FORMAT).date()
    except ValueError:
        return None


def interpret_kerala_fact_values(
    memory_discovery: MemoryDiscoveryResult,
) -> KeralaFactRecallResult:
    """Interpret recalled values without hiding relevant malformed evidence."""
    failures = list(memory_discovery.failures)
    uncertainty = list(memory_discovery.uncertainty)
    known: dict[str, KeralaLotteryFact] = {}
    matching = 0
    usable = 0

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
                f"Kerala collection evidence {source or f'at value {index}'} "
                f"has unusable execution status: {execution_status}"
            )
            continue
        if not source:
            uncertainty.append(
                f"Kerala collection evidence at value {index} has no source"
            )
            continue

        data = outcome.get("data")
        parsed = data.get("parsed") if isinstance(data, dict) else None
        if not isinstance(parsed, dict):
            uncertainty.append(
                f"Kerala collection evidence {source} has no object parsed payload"
            )
            continue

        draw_date = _parse_draw_date(parsed.get("draw_date"))
        lottery_name = " ".join(str(parsed.get("lottery_name") or "").split())
        if draw_date is None:
            uncertainty.append(
                f"Kerala collection evidence {source} has no usable draw date"
            )
            continue
        if not lottery_name or lottery_name == "Unknown":
            uncertainty.append(
                f"Kerala collection evidence {source} has no usable lottery name"
            )
            continue

        usable += 1
        # Discovery order is storage order; later corrections win for one source.
        known[source] = KeralaLotteryFact(
            source=source,
            draw_date=draw_date,
            lottery_name=lottery_name,
        )

    if memory_discovery.status == "failed":
        status = "failed"
    elif failures or uncertainty or memory_discovery.status != "success":
        status = "partial"
    else:
        status = "success"

    return KeralaFactRecallResult(
        status=status,
        facts=tuple(sorted(known.values(), key=lambda item: (item.draw_date, item.source))),
        memory_discovery=memory_discovery,
        examined_values=len(memory_discovery.values),
        matching_collection_values=matching,
        usable_matching_values=usable,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )


def recall_kerala_facts_result(
    memory_path: str | Path | None = None,
) -> KeralaFactRecallResult:
    """Recall Kerala Lottery facts and return the complete interpretation receipt."""
    target = Path(memory_path) if memory_path is not None else living_memory_path()
    with Memory(target) as memory:
        discovery = discover_preserved_values(memory, requester="nokku")
    return interpret_kerala_fact_values(discovery)


def recall_kerala_facts(
    memory_path: str | Path | None = None,
) -> tuple[KeralaLotteryFact, ...]:
    """Compatibility helper returning only facts from the truthful recall receipt."""
    return recall_kerala_facts_result(memory_path).facts
