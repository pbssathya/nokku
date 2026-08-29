"""Living Kerala Lottery decision loop.

Nokku recalls preserved official facts from COSsse Memory, refreshes only the
small current numeric frontier when it is stale, applies the application-owned
weekly participation policy, and preserves the decision experience.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Callable
from zoneinfo import ZoneInfo

from collector.collect import collect
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory

from nokku.preferences import (
    KeralaLotteryPreferences,
    UserPreferences,
    load_kerala_lottery_preferences,
    load_user_preferences,
    save_kerala_lottery_preferences,
    save_user_preferences,
    validate_timezone_name,
)
from nokku.memory_flow import MemoryPreservationResult, preserve_meaning
from nokku.runtime import living_memory_path

from .astrology import VimshottariSnapshot
from .astrology_signal import (
    AstrologyObservationResult,
    lakshmi_astrology_observation_result,
)
from .decision import (
    KeralaLotteryDecision,
    KeralaLotteryFact,
    decide_weekly_participation,
    resolve_week,
)
from .fact_recall import KeralaFactRecallResult, recall_kerala_facts_result
from .numerology import LakshmiNumerologySignal, lakshmi_numerology_signal


DOMAIN = "games/chance/lottery/kerala"
SCHEDULE_DOMAIN = f"{DOMAIN}/schedule"
SCHEDULE_SOURCE = "upcoming"
KERALA_TIMEZONE_NAME = "Asia/Kolkata"
KERALA_TIMEZONE = ZoneInfo(KERALA_TIMEZONE_NAME)


class MissingUserTimezoneError(RuntimeError):
    """Raised when an undated user request has no resolvable local timezone."""


@dataclass(frozen=True, slots=True)
class FrontierRefreshResult:
    """Truthful receipt for one current-result frontier refresh attempt."""

    status: str
    refreshed_sources: tuple[str, ...]
    attempted_sources: tuple[str, ...]
    checkpoint_source: str | None
    checkpoint_draw_date: date | None
    stop_reason: str
    preservation_attempts: tuple[MemoryPreservationResult, ...] = ()
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScheduleCollectionResult:
    """Truthful lower-layer receipt for one official schedule collection attempt."""

    status: str
    dates: tuple[date, ...]
    draw_numbers: dict[date, str]
    disposition_status: str
    execution_status: str | None
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LivingDecisionResult:
    decision: KeralaLotteryDecision
    decision_date: date
    memory_id: str | None
    decision_preservation: MemoryPreservationResult
    refreshed_sources: tuple[str, ...]
    frontier_refresh: FrontierRefreshResult | None
    fact_recall: KeralaFactRecallResult
    week_start_preference: str
    user_timezone: str | None
    scheduled_draw_dates: tuple[date, ...]
    schedule_collection: ScheduleCollectionResult | None
    numerology_signals: tuple[LakshmiNumerologySignal, ...]
    astrology_observation: VimshottariSnapshot | None
    astrology_observation_result: AstrologyObservationResult | None


def local_today(timezone_name: str, now: datetime | None = None) -> date:
    """Return today's date in an explicit IANA timezone."""
    normalized = validate_timezone_name(timezone_name)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("local_today() requires an aware datetime when now is supplied")
    return current.astimezone(ZoneInfo(normalized)).date()


def kerala_today(now: datetime | None = None) -> date:
    """Return the current calendar date for the Kerala Lottery domain."""
    return local_today(KERALA_TIMEZONE_NAME, now)


def _parse_draw_date(value: object) -> date | None:
    text = str(value or "")
    if not text or text == "Unknown":
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def _draw_number_from_code(value: object) -> str | None:
    """Extract the numeric draw number from an official code such as SS-534."""
    match = re.search(r"(\d+)\s*$", str(value or ""))
    return match.group(1) if match else None


def _disposition_status_text(status: object) -> str:
    value = getattr(status, "value", None)
    return str(value if value is not None else status)


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
    """Compatibility helper returning facts from the truthful recall receipt."""
    return recall_kerala_facts_result(memory_path).facts


def refresh_current_frontier_result(
    *,
    anchor: date,
    facts: tuple[KeralaLotteryFact, ...],
    memory_path: str | Path | None = None,
    max_new_sources: int = 7,
    collector: Callable = collect,
) -> FrontierRefreshResult:
    """Refresh the numeric frontier and report exactly why the attempt stopped."""
    numeric_facts = tuple(fact for fact in facts if fact.source.isdigit())
    checkpoint_source = (
        str(max(int(fact.source) for fact in numeric_facts)) if numeric_facts else None
    )
    checkpoint_draw_date = max((fact.draw_date for fact in facts), default=None)

    if max_new_sources < 1:
        return FrontierRefreshResult(
            status="invalid_input",
            refreshed_sources=(),
            attempted_sources=(),
            checkpoint_source=checkpoint_source,
            checkpoint_draw_date=checkpoint_draw_date,
            stop_reason="invalid_max_new_sources",
            failures=("max_new_sources must be at least 1",),
        )

    if checkpoint_source is None or checkpoint_draw_date is None:
        return FrontierRefreshResult(
            status="unavailable",
            refreshed_sources=(),
            attempted_sources=(),
            checkpoint_source=checkpoint_source,
            checkpoint_draw_date=checkpoint_draw_date,
            stop_reason="no_numeric_frontier",
            failures=("no usable numeric source/date frontier is available",),
        )

    if checkpoint_draw_date >= anchor:
        return FrontierRefreshResult(
            status="current",
            refreshed_sources=(),
            attempted_sources=(),
            checkpoint_source=checkpoint_source,
            checkpoint_draw_date=checkpoint_draw_date,
            stop_reason="checkpoint_current_through_anchor",
        )

    target = Path(memory_path) if memory_path is not None else living_memory_path()
    adapter = CollectorAdapter(collector)
    refreshed: list[str] = []
    attempted: list[str] = []
    preservation_attempts: list[MemoryPreservationResult] = []
    uncertainty: list[str] = []
    source_id = int(checkpoint_source) + 1
    latest_usable_date = checkpoint_draw_date

    for _ in range(max_new_sources):
        source = str(source_id)
        attempted.append(source)

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
        disposition_status = _disposition_status_text(disposition.status)

        if (
            disposition.status != DispositionStatus.CLAIMED
            or len(disposition.feedback) != 1
        ):
            return FrontierRefreshResult(
                status="partial" if refreshed else "failed",
                refreshed_sources=tuple(refreshed),
                attempted_sources=tuple(attempted),
                checkpoint_source=checkpoint_source,
                checkpoint_draw_date=checkpoint_draw_date,
                stop_reason="collector_not_singly_claimed",
                preservation_attempts=tuple(preservation_attempts),
                failures=(
                    f"source {source} was not singly claimed: "
                    f"disposition={disposition_status}, "
                    f"feedback_count={len(disposition.feedback)}",
                ),
                uncertainty=tuple(uncertainty),
            )

        collected_meaning = disposition.feedback[0]
        report = collected_meaning.body.get("outcome") or {}
        execution_status = str(
            (report.get("execution") or {}).get("status") or "unknown"
        )

        if execution_status not in ("success", "partial"):
            return FrontierRefreshResult(
                status="partial" if refreshed else "failed",
                refreshed_sources=tuple(refreshed),
                attempted_sources=tuple(attempted),
                checkpoint_source=checkpoint_source,
                checkpoint_draw_date=checkpoint_draw_date,
                stop_reason="collector_execution_not_usable",
                preservation_attempts=tuple(preservation_attempts),
                failures=(
                    f"source {source} collector execution status: "
                    f"{execution_status}",
                ),
                uncertainty=tuple(uncertainty),
            )

        parsed = (report.get("data") or {}).get("parsed") or {}
        draw_date = _parse_draw_date(parsed.get("draw_date"))
        lottery_name = " ".join(
            str(parsed.get("lottery_name") or "").split()
        )

        if draw_date is None or not lottery_name or lottery_name == "Unknown":
            return FrontierRefreshResult(
                status="partial" if refreshed else "failed",
                refreshed_sources=tuple(refreshed),
                attempted_sources=tuple(attempted),
                checkpoint_source=checkpoint_source,
                checkpoint_draw_date=checkpoint_draw_date,
                stop_reason="collector_payload_not_usable",
                preservation_attempts=tuple(preservation_attempts),
                failures=(
                    f"source {source} did not contain a usable draw date/name",
                ),
                uncertainty=tuple(uncertainty),
            )

        if draw_date > anchor:
            return FrontierRefreshResult(
                status="success" if refreshed else "current",
                refreshed_sources=tuple(refreshed),
                attempted_sources=tuple(attempted),
                checkpoint_source=checkpoint_source,
                checkpoint_draw_date=checkpoint_draw_date,
                stop_reason="next_draw_after_anchor",
                preservation_attempts=tuple(preservation_attempts),
                uncertainty=tuple(uncertainty),
            )

        # Collection and preservation are separate handoffs.
        # Do not call a collected source "refreshed" until Memory reports
        # a successful preservation receipt.
        with Memory(target) as memory:
            preservation = preserve_meaning(memory, collected_meaning)

        preservation_attempts.append(preservation)

        if preservation.status != "success":
            combined_uncertainty = (
                tuple(uncertainty) + tuple(preservation.uncertainty)
            )
            return FrontierRefreshResult(
                status=(
                    "partial"
                    if refreshed or preservation.status == "partial"
                    else "failed"
                ),
                refreshed_sources=tuple(refreshed),
                attempted_sources=tuple(attempted),
                checkpoint_source=checkpoint_source,
                checkpoint_draw_date=checkpoint_draw_date,
                stop_reason="memory_preservation_not_successful",
                preservation_attempts=tuple(preservation_attempts),
                failures=tuple(preservation.failures),
                uncertainty=combined_uncertainty,
            )

        refreshed.append(source)
        latest_usable_date = draw_date

        if execution_status == "partial":
            uncertainty.append(
                f"source {source} collector reported partial execution"
            )

        if draw_date >= anchor:
            return FrontierRefreshResult(
                status="partial" if uncertainty else "success",
                refreshed_sources=tuple(refreshed),
                attempted_sources=tuple(attempted),
                checkpoint_source=checkpoint_source,
                checkpoint_draw_date=checkpoint_draw_date,
                stop_reason="anchor_reached",
                preservation_attempts=tuple(preservation_attempts),
                uncertainty=tuple(uncertainty),
            )

        source_id += 1

    return FrontierRefreshResult(
        status="partial" if latest_usable_date < anchor else "success",
        refreshed_sources=tuple(refreshed),
        attempted_sources=tuple(attempted),
        checkpoint_source=checkpoint_source,
        checkpoint_draw_date=checkpoint_draw_date,
        stop_reason="max_new_sources_reached",
        preservation_attempts=tuple(preservation_attempts),
        uncertainty=(
            tuple(uncertainty)
            + (
                ("frontier limit reached before anchor",)
                if latest_usable_date < anchor
                else ()
            )
        ),
    )
def refresh_current_frontier(
    *,
    anchor: date,
    facts: tuple[KeralaLotteryFact, ...],
    memory_path: str | Path | None = None,
    max_new_sources: int = 7,
    collector: Callable = collect,
) -> tuple[str, ...]:
    """Compatibility helper returning only refreshed source ids."""
    return refresh_current_frontier_result(
        anchor=anchor,
        facts=facts,
        memory_path=memory_path,
        max_new_sources=max_new_sources,
        collector=collector,
    ).refreshed_sources


def collect_upcoming_draw_schedule(
    *, collector: Callable = collect
) -> ScheduleCollectionResult:
    """Collect official upcoming dates and report exactly what the layer observed."""
    disposition = Flow().encounter(
        Meaning(
            body={
                "need": "collect",
                "domain_path": SCHEDULE_DOMAIN,
                "source": SCHEDULE_SOURCE,
                "store": False,
                "requester": "nokku",
            }
        ),
        [CollectorAdapter(collector)],
    )
    disposition_status = _disposition_status_text(disposition.status)
    if disposition.status != DispositionStatus.CLAIMED or len(disposition.feedback) != 1:
        return ScheduleCollectionResult(
            status="unavailable",
            dates=(),
            draw_numbers={},
            disposition_status=disposition_status,
            execution_status=None,
            failures=(
                f"schedule collection was not singly claimed: disposition={disposition_status}, "
                f"feedback_count={len(disposition.feedback)}",
            ),
        )

    report = disposition.feedback[0].body.get("outcome") or {}
    execution_status = str((report.get("execution") or {}).get("status") or "unknown")
    if execution_status not in ("success", "partial"):
        return ScheduleCollectionResult(
            status="failed",
            dates=(),
            draw_numbers={},
            disposition_status=disposition_status,
            execution_status=execution_status,
            failures=(f"schedule collector execution status: {execution_status}",),
        )

    parsed = (report.get("data") or {}).get("parsed") or {}
    raw_draws = parsed.get("upcoming_draws")
    if not isinstance(raw_draws, list):
        return ScheduleCollectionResult(
            status="partial",
            dates=(),
            draw_numbers={},
            disposition_status=disposition_status,
            execution_status=execution_status,
            uncertainty=("schedule payload has no usable upcoming_draws list",),
        )

    dates: set[date] = set()
    draw_numbers: dict[date, str] = {}
    invalid_entries = 0
    for item in raw_draws:
        if not isinstance(item, dict):
            invalid_entries += 1
            continue
        try:
            draw_date = date.fromisoformat(str(item.get("draw_date") or ""))
        except ValueError:
            invalid_entries += 1
            continue
        dates.add(draw_date)
        draw_number = _draw_number_from_code(item.get("draw_code"))
        if draw_number is not None:
            draw_numbers[draw_date] = draw_number

    uncertainty: tuple[str, ...] = ()
    status = execution_status
    if invalid_entries:
        status = "partial"
        uncertainty = (f"ignored {invalid_entries} malformed upcoming draw entrie(s)",)
    elif execution_status == "partial":
        uncertainty = ("collector reported a partial schedule result",)

    return ScheduleCollectionResult(
        status=status,
        dates=tuple(sorted(dates)),
        draw_numbers=draw_numbers,
        disposition_status=disposition_status,
        execution_status=execution_status,
        uncertainty=uncertainty,
    )


def collect_upcoming_draw_dates(*, collector: Callable = collect) -> tuple[date, ...]:
    """Compatibility helper returning only currently listed official draw dates."""
    return collect_upcoming_draw_schedule(collector=collector).dates


def _numerology_signals_for_candidates(
    *,
    user_preferences: UserPreferences,
    candidate_dates: tuple[date, ...],
    draw_numbers: dict[date, str] | None = None,
) -> tuple[LakshmiNumerologySignal, ...]:
    """Calculate explainable numerology observations for eligible candidate dates."""
    if user_preferences.birth is None:
        return ()

    birth_date = date.fromisoformat(user_preferences.birth.date)
    numbers = draw_numbers or {}
    return tuple(
        lakshmi_numerology_signal(
            birth_date=birth_date,
            target=candidate,
            draw_number=numbers.get(candidate),
        )
        for candidate in sorted(set(candidate_dates))
    )


def _numerology_signals_for_decision(
    *,
    user_preferences: UserPreferences,
    decision: KeralaLotteryDecision,
    draw_numbers: dict[date, str] | None = None,
) -> tuple[LakshmiNumerologySignal, ...]:
    """Fallback observation for preferred/backup dates when no schedule candidates exist."""
    candidates = tuple(
        candidate
        for candidate in (decision.preferred_date, decision.backup_date)
        if candidate is not None
    )
    return _numerology_signals_for_candidates(
        user_preferences=user_preferences,
        candidate_dates=candidates,
        draw_numbers=draw_numbers,
    )


def _numerology_priority(
    signals: tuple[LakshmiNumerologySignal, ...],
) -> dict[date, tuple[int, int, int]]:
    """Convert recovered selection observations into a lexicographic priority.

    This is an explicitly experimental evolution, not a reconstructed historical
    score. It uses only signals that the recovered Lakshmi analysis actually
    described: personal-day 3/6/9 alignment, exact personal-number matches, and
    draw-number 3/6/9 alignment.
    """
    priorities: dict[date, tuple[int, int, int]] = {}
    for signal in signals:
        exact_match = (
            signal.personal_day_matches_birth_number
            or signal.personal_day_matches_life_path
            or signal.personal_day_matches_personal_year
        )
        priorities[signal.target_date] = (
            int(signal.personal_day_in_369_family),
            int(exact_match),
            int(signal.draw_in_369_family),
        )
    return priorities


def _numerology_signal_payload(signal: LakshmiNumerologySignal) -> dict[str, object]:
    return {
        "target_date": signal.target_date.isoformat(),
        "birth_number": signal.birth_number,
        "life_path": signal.life_path,
        "personal_year": signal.personal_year,
        "personal_month_compound": signal.personal_month_compound,
        "personal_month": signal.personal_month,
        "personal_day_compound": signal.personal_day_compound,
        "personal_day": signal.personal_day,
        "draw_number": signal.draw_number,
        "draw_reduction": signal.draw_reduction,
        "personal_day_in_369_family": signal.personal_day_in_369_family,
    }


def _astrology_signal_payload(signal: VimshottariSnapshot) -> dict[str, object]:
    return {
        "natal_nakshatra": signal.natal_nakshatra,
        "natal_nakshatra_lord": signal.natal_nakshatra_lord,
        "mahadasha": signal.mahadasha,
        "antardasha": signal.antardasha,
        "mahadasha_start": signal.mahadasha_start.isoformat(),
        "mahadasha_end": signal.mahadasha_end.isoformat(),
        "antardasha_start": signal.antardasha_start.isoformat(),
        "antardasha_end": signal.antardasha_end.isoformat(),
        "status": signal.status,
    }


def _memory_preservation_payload(
    result: MemoryPreservationResult,
) -> dict[str, object]:
    stored_at = result.stored_at
    if isinstance(stored_at, (date, datetime)):
        stored_at = stored_at.isoformat()
    elif stored_at is not None and not isinstance(
        stored_at, (str, int, float, bool)
    ):
        stored_at = str(stored_at)

    return {
        "status": result.status,
        "memory_id": result.memory_id,
        "disposition_status": result.disposition_status,
        "feedback_count": result.feedback_count,
        "memory_event": result.memory_event,
        "stored_at": stored_at,
        "sha256": result.sha256,
        "failures": list(result.failures),
        "uncertainty": list(result.uncertainty),
    }


def _frontier_refresh_payload(
    result: FrontierRefreshResult | None,
) -> dict[str, object]:
    if result is None:
        return {"status": "not_requested"}
    return {
        "status": result.status,
        "checkpoint_source": result.checkpoint_source,
        "checkpoint_draw_date": (
            result.checkpoint_draw_date.isoformat()
            if result.checkpoint_draw_date is not None
            else None
        ),
        "attempted_sources": list(result.attempted_sources),
        "refreshed_sources": list(result.refreshed_sources),
        "stop_reason": result.stop_reason,
        "preservation_attempts": [
            _memory_preservation_payload(attempt)
            for attempt in result.preservation_attempts
        ],
        "failures": list(result.failures),
        "uncertainty": list(result.uncertainty),
    }


def _fact_recall_payload(
    result: KeralaFactRecallResult,
) -> dict[str, object]:
    memory = result.memory_discovery
    return {
        "status": result.status,
        "fact_count": len(result.facts),
        "examined_values": result.examined_values,
        "matching_collection_values": result.matching_collection_values,
        "usable_matching_values": result.usable_matching_values,
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


def _schedule_collection_payload(
    result: ScheduleCollectionResult | None,
) -> dict[str, object]:
    if result is None:
        return {"status": "not_requested"}
    return {
        "status": result.status,
        "disposition_status": result.disposition_status,
        "execution_status": result.execution_status,
        "failures": list(result.failures),
        "uncertainty": list(result.uncertainty),
        "draw_count": len(result.dates),
        "draw_dates": [item.isoformat() for item in result.dates],
    }


def _astrology_observation_payload(
    result: AstrologyObservationResult | None,
) -> dict[str, object]:
    if result is None:
        return {"status": "not_requested"}
    return {
        "status": result.status,
        "natal_moon_longitude": result.natal_moon_longitude,
        "failures": list(result.failures),
        "uncertainty": list(result.uncertainty),
    }


def preserve_decision_experience(
    *,
    request: str,
    anchor: date,
    decision: KeralaLotteryDecision,
    user_timezone: str | None = None,
    frontier_refresh: FrontierRefreshResult | None = None,
    fact_recall: KeralaFactRecallResult,
    scheduled_draw_dates: tuple[date, ...] = (),
    schedule_collection: ScheduleCollectionResult | None = None,
    numerology_signals: tuple[LakshmiNumerologySignal, ...] = (),
    astrology_observation: VimshottariSnapshot | None = None,
    astrology_observation_result: AstrologyObservationResult | None = None,
    memory_path: str | Path | None = None,
) -> MemoryPreservationResult:
    target = Path(memory_path) if memory_path is not None else living_memory_path()
    experience = Meaning(
        body={
            "experience": "decision",
            "application": "nokku",
            "domain_path": DOMAIN,
            "decision_type": "weekly_participation",
            "request": request,
            "anchor_date": anchor.isoformat(),
            "user_timezone": user_timezone,
            "operational_context": {
                "current_result_frontier_refresh": _frontier_refresh_payload(
                    frontier_refresh
                ),
                "kerala_fact_recall": _fact_recall_payload(fact_recall),
                "official_upcoming_draw_dates": [
                    item.isoformat() for item in scheduled_draw_dates
                ],
                "official_upcoming_draw_schedule_collection": _schedule_collection_payload(
                    schedule_collection
                ),
                "astrology_observation_attempt": _astrology_observation_payload(
                    astrology_observation_result
                ),
            },
            "signals": {
                "numerology": [
                    _numerology_signal_payload(signal) for signal in numerology_signals
                ],
                "astrology": (
                    _astrology_signal_payload(astrology_observation)
                    if astrology_observation is not None
                    else None
                ),
            },
            "decision": decision.to_dict(),
        }
    )
    with Memory(target) as memory:
        return preserve_meaning(memory, experience)


def run_weekly_decision(
    request: str,
    *,
    anchor: date | None = None,
    timezone_override: str | None = None,
    remember_timezone: bool = False,
    week_start_override: str | None = None,
    remember_week_start: bool = False,
    refresh: bool = True,
    memory_path: str | Path | None = None,
    preferences_path: str | Path | None = None,
    collector: Callable = collect,
    astrology_target_at: datetime | None = None,
    astrology_natal_moon_longitude: float | None = None,
    now: datetime | None = None,
) -> LivingDecisionResult:
    memory_target = Path(memory_path) if memory_path is not None else living_memory_path()

    user_preferences = load_user_preferences(preferences_path)
    user_timezone = user_preferences.timezone
    if timezone_override is not None:
        user_timezone = validate_timezone_name(timezone_override)
        if remember_timezone:
            save_user_preferences(UserPreferences(timezone=user_timezone), preferences_path)
            user_preferences = load_user_preferences(preferences_path)

    if anchor is None:
        if user_timezone is None:
            raise MissingUserTimezoneError(
                "Nokku needs the user's timezone to understand an undated local request."
            )
        anchor_date = local_today(user_timezone, now)
    else:
        anchor_date = anchor

    preferences = load_kerala_lottery_preferences(preferences_path)
    week_start = week_start_override.lower() if week_start_override else preferences.decision_week_start
    if week_start_override and remember_week_start:
        save_kerala_lottery_preferences(
            KeralaLotteryPreferences(decision_week_start=week_start),
            preferences_path,
        )

    fact_recall = recall_kerala_facts_result(memory_target)
    facts = fact_recall.facts
    refreshed: tuple[str, ...] = ()
    frontier_refresh: FrontierRefreshResult | None = None
    scheduled_draw_dates: tuple[date, ...] = ()
    scheduled_draw_numbers: dict[date, str] = {}
    schedule_collection: ScheduleCollectionResult | None = None
    eligible_dates: tuple[date, ...] | None = None
    if refresh:
        frontier_refresh = refresh_current_frontier_result(
            anchor=anchor_date,
            facts=facts,
            memory_path=memory_target,
            collector=collector,
        )
        refreshed = frontier_refresh.refreshed_sources
        if refreshed:
            fact_recall = recall_kerala_facts_result(memory_target)
            facts = fact_recall.facts
        schedule_collection = collect_upcoming_draw_schedule(collector=collector)
        scheduled_draw_dates = schedule_collection.dates
        scheduled_draw_numbers = schedule_collection.draw_numbers
        eligible_dates = scheduled_draw_dates

    resolved_week_start, resolved_week_end = resolve_week(anchor_date, week_start)
    earliest = max(anchor_date, resolved_week_start)
    scheduled_candidates = tuple(
        candidate
        for candidate in scheduled_draw_dates
        if earliest <= candidate <= resolved_week_end
    )
    candidate_numerology = _numerology_signals_for_candidates(
        user_preferences=user_preferences,
        candidate_dates=scheduled_candidates,
        draw_numbers=scheduled_draw_numbers,
    )
    numerology_priority = _numerology_priority(candidate_numerology)

    decision = decide_weekly_participation(
        request,
        anchor=anchor_date,
        facts=facts,
        week_start_name=week_start,
        eligible_dates=eligible_dates,
        eligible_dates_status=(schedule_collection.status if schedule_collection is not None else None),
        numerology_priority=numerology_priority or None,
    )
    numerology_signals = candidate_numerology or _numerology_signals_for_decision(
        user_preferences=user_preferences,
        decision=decision,
        draw_numbers=scheduled_draw_numbers,
    )

    astrology_observation_result = (
        lakshmi_astrology_observation_result(
            user_preferences=user_preferences,
            target_at=astrology_target_at,
            natal_moon_longitude=astrology_natal_moon_longitude,
        )
        if astrology_target_at is not None
        else None
    )
    astrology_observation = (
        astrology_observation_result.observation
        if astrology_observation_result is not None
        else None
    )

    decision_preservation = preserve_decision_experience(
        request=request,
        anchor=anchor_date,
        decision=decision,
        user_timezone=user_timezone,
        frontier_refresh=frontier_refresh,
        fact_recall=fact_recall,
        scheduled_draw_dates=scheduled_draw_dates,
        schedule_collection=schedule_collection,
        numerology_signals=numerology_signals,
        astrology_observation=astrology_observation,
        astrology_observation_result=astrology_observation_result,
        memory_path=memory_target,
    )
    memory_id = decision_preservation.memory_id

    return LivingDecisionResult(
        decision=decision,
        decision_date=anchor_date,
        memory_id=memory_id,
        decision_preservation=decision_preservation,
        refreshed_sources=refreshed,
        frontier_refresh=frontier_refresh,
        fact_recall=fact_recall,
        week_start_preference=week_start,
        user_timezone=user_timezone,
        scheduled_draw_dates=scheduled_draw_dates,
        schedule_collection=schedule_collection,
        numerology_signals=numerology_signals,
        astrology_observation=astrology_observation,
        astrology_observation_result=astrology_observation_result,
    )
