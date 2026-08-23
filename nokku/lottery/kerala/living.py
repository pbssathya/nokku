"""Living Kerala Lottery decision loop.

Nokku recalls preserved official facts from COSsse Memory, refreshes only the
small current numeric frontier when it is stale, applies the application-owned
weekly participation policy, and preserves the decision experience.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from collector.collect import collect
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory

from nokku.preferences import (
    KeralaLotteryPreferences,
    load_kerala_lottery_preferences,
    save_kerala_lottery_preferences,
)
from nokku.runtime import living_memory_path

from .decision import KeralaLotteryDecision, KeralaLotteryFact, decide_weekly_participation


DOMAIN = "games/chance/lottery/kerala"


@dataclass(frozen=True, slots=True)
class LivingDecisionResult:
    decision: KeralaLotteryDecision
    memory_id: str
    refreshed_sources: tuple[str, ...]
    week_start_preference: str


def _parse_draw_date(value: object) -> date | None:
    text = str(value or "")
    if not text or text == "Unknown":
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def _discover_values(memory: Memory):
    flow = Flow()
    adapter = MemoryAdapter(memory)
    discovery = flow.encounter(
        Meaning(body={"need": "discover_preserved_experiences", "requester": "nokku"}),
        [adapter],
    )
    assert discovery.status == DispositionStatus.CLAIMED
    assert len(discovery.feedback) == 1

    for receipt in discovery.feedback[0].body.get("receipts", []):
        recalled = flow.encounter(
            Meaning(
                body={
                    "need": "recall_preserved_experience",
                    "memory_id": receipt["memory_id"],
                    "requester": "nokku",
                }
            ),
            [adapter],
        )
        assert recalled.status == DispositionStatus.CLAIMED
        assert len(recalled.feedback) == 1
        value = recalled.feedback[0].body.get("value")
        if value:
            yield value


def recall_kerala_facts(memory_path: str | Path | None = None) -> tuple[KeralaLotteryFact, ...]:
    target = Path(memory_path) if memory_path is not None else living_memory_path()
    known: dict[str, KeralaLotteryFact] = {}

    with Memory(target) as memory:
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

            source = str(request.get("source", ""))
            if not source:
                continue

            parsed = (outcome.get("data") or {}).get("parsed") or {}
            draw_date = _parse_draw_date(parsed.get("draw_date"))
            lottery_name = " ".join(str(parsed.get("lottery_name") or "").split())
            if draw_date is None or not lottery_name or lottery_name == "Unknown":
                continue

            # Receipt order is storage order; later corrections win for one source.
            known[source] = KeralaLotteryFact(
                source=source,
                draw_date=draw_date,
                lottery_name=lottery_name,
            )

    return tuple(sorted(known.values(), key=lambda item: (item.draw_date, item.source)))


def _preserve_meaning(meaning: Meaning, memory_path: Path) -> str:
    with Memory(memory_path) as memory:
        disposition = Flow().encounter(meaning, [MemoryAdapter(memory)])
    assert disposition.status == DispositionStatus.CLAIMED
    assert len(disposition.feedback) == 1
    return str(disposition.feedback[0].body["memory_id"])


def refresh_current_frontier(
    *,
    anchor: date,
    facts: tuple[KeralaLotteryFact, ...],
    memory_path: str | Path | None = None,
    max_new_sources: int = 7,
    collector: Callable = collect,
) -> tuple[str, ...]:
    """Refresh only the small current numeric frontier when Memory is stale.

    This is not a historical traversal mechanism. It starts immediately after
    the highest remembered modern numeric source and stops at the first source
    that is not a usable published draw.
    """
    if max_new_sources < 1:
        return ()

    target = Path(memory_path) if memory_path is not None else living_memory_path()
    numeric = [int(fact.source) for fact in facts if fact.source.isdigit()]
    latest_date = max((fact.draw_date for fact in facts), default=None)

    if not numeric or latest_date is None or latest_date >= anchor:
        return ()

    adapter = CollectorAdapter(collector)
    refreshed: list[str] = []
    source_id = max(numeric) + 1

    for _ in range(max_new_sources):
        source = str(source_id)
        disposition = Flow().encounter(
            Meaning(
                body={
                    "need": "collect",
                    "domain_path": DOMAIN,
                    "source": source,
                    "store": False,
                    "requester": "nokku",
                }
            ),
            [adapter],
        )
        if disposition.status != DispositionStatus.CLAIMED or len(disposition.feedback) != 1:
            break

        result = disposition.feedback[0]
        report = result.body.get("outcome") or {}
        status = (report.get("execution") or {}).get("status")
        if status not in ("success", "partial"):
            break

        parsed = (report.get("data") or {}).get("parsed") or {}
        draw_date = _parse_draw_date(parsed.get("draw_date"))
        lottery_name = " ".join(str(parsed.get("lottery_name") or "").split())
        if draw_date is None or not lottery_name or lottery_name == "Unknown":
            break
        if draw_date > anchor:
            break

        _preserve_meaning(result, target)
        refreshed.append(source)
        source_id += 1

    return tuple(refreshed)


def preserve_decision_experience(
    *,
    request: str,
    anchor: date,
    decision: KeralaLotteryDecision,
    memory_path: str | Path | None = None,
) -> str:
    target = Path(memory_path) if memory_path is not None else living_memory_path()
    experience = Meaning(
        body={
            "experience": "decision",
            "application": "nokku",
            "domain_path": DOMAIN,
            "decision_type": "weekly_participation",
            "request": request,
            "anchor_date": anchor.isoformat(),
            "decision": decision.to_dict(),
        }
    )
    return _preserve_meaning(experience, target)


def run_weekly_decision(
    request: str,
    *,
    anchor: date | None = None,
    week_start_override: str | None = None,
    remember_week_start: bool = False,
    refresh: bool = True,
    memory_path: str | Path | None = None,
    preferences_path: str | Path | None = None,
    collector: Callable = collect,
) -> LivingDecisionResult:
    anchor_date = anchor or date.today()
    memory_target = Path(memory_path) if memory_path is not None else living_memory_path()

    preferences = load_kerala_lottery_preferences(preferences_path)
    week_start = week_start_override.lower() if week_start_override else preferences.decision_week_start
    if week_start_override and remember_week_start:
        save_kerala_lottery_preferences(
            KeralaLotteryPreferences(decision_week_start=week_start),
            preferences_path,
        )

    facts = recall_kerala_facts(memory_target)
    refreshed: tuple[str, ...] = ()
    if refresh:
        refreshed = refresh_current_frontier(
            anchor=anchor_date,
            facts=facts,
            memory_path=memory_target,
            collector=collector,
        )
        if refreshed:
            facts = recall_kerala_facts(memory_target)

    decision = decide_weekly_participation(
        request,
        anchor=anchor_date,
        facts=facts,
        week_start_name=week_start,
    )
    memory_id = preserve_decision_experience(
        request=request,
        anchor=anchor_date,
        decision=decision,
        memory_path=memory_target,
    )

    return LivingDecisionResult(
        decision=decision,
        memory_id=memory_id,
        refreshed_sources=refreshed,
        week_start_preference=week_start,
    )
