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
from .numerology import LakshmiNumerologySignal, lakshmi_numerology_signal


DOMAIN = "games/chance/lottery/kerala"
SCHEDULE_DOMAIN = f"{DOMAIN}/schedule"
SCHEDULE_SOURCE = "upcoming"
KERALA_TIMEZONE_NAME = "Asia/Kolkata"
KERALA_TIMEZONE = ZoneInfo(KERALA_TIMEZONE_NAME)


class MissingUserTimezoneError(RuntimeError):
    """Raised when an undated user request has no resolvable local timezone."""


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
    memory_id: str
    refreshed_sources: tuple[str, ...]
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
    scheduled_draw_dates: tuple[date, ...] = (),
    schedule_collection: ScheduleCollectionResult | None = None,
    numerology_signals: tuple[LakshmiNumerologySignal, ...] = (),
    astrology_observation: VimshottariSnapshot | None = None,
    astrology_observation_result: AstrologyObservationResult | None = None,
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
            "user_timezone": user_timezone,
            "operational_context": {
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
    return _preserve_meaning(experience, target)


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

    facts = recall_kerala_facts(memory_target)
    refreshed: tuple[str, ...] = ()
    scheduled_draw_dates: tuple[date, ...] = ()
    scheduled_draw_numbers: dict[date, str] = {}
    schedule_collection: ScheduleCollectionResult | None = None
    eligible_dates: tuple[date, ...] | None = None
    if refresh:
        refreshed = refresh_current_frontier(
            anchor=anchor_date,
            facts=facts,
            memory_path=memory_target,
            collector=collector,
        )
        if refreshed:
            facts = recall_kerala_facts(memory_target)
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

    memory_id = preserve_decision_experience(
        request=request,
        anchor=anchor_date,
        decision=decision,
        user_timezone=user_timezone,
        scheduled_draw_dates=scheduled_draw_dates,
        schedule_collection=schedule_collection,
        numerology_signals=numerology_signals,
        astrology_observation=astrology_observation,
        astrology_observation_result=astrology_observation_result,
        memory_path=memory_target,
    )

    return LivingDecisionResult(
        decision=decision,
        decision_date=anchor_date,
        memory_id=memory_id,
        refreshed_sources=refreshed,
        week_start_preference=week_start,
        user_timezone=user_timezone,
        scheduled_draw_dates=scheduled_draw_dates,
        schedule_collection=schedule_collection,
        numerology_signals=numerology_signals,
        astrology_observation=astrology_observation,
        astrology_observation_result=astrology_observation_result,
    )
