"""Application-specific weekly participation decision for Kerala Lottery.

This deliberately does not pretend that historical lottery results predict a
future winning draw. Nokku uses history to understand the living habitat and
operational context; the participation recommendation remains conservative and
user-overridable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta
import re
from typing import Iterable, Literal, Mapping


WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass(frozen=True, slots=True)
class KeralaLotteryFact:
    source: str
    draw_date: date
    lottery_name: str


@dataclass(frozen=True, slots=True)
class KeralaLotteryDecision:
    recommendation: Literal["BUY", "SKIP"]
    week_start: date
    week_end: date
    preferred_date: date | None
    backup_date: date | None
    preferred_time: str
    evidence_summary: tuple[str, ...]
    uncertainty: str
    override: Literal["BUY", "SKIP"] | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        for key in ("week_start", "week_end", "preferred_date", "backup_date"):
            value = data[key]
            data[key] = value.isoformat() if value is not None else None
        return data


def resolve_week(anchor: date, week_start_name: str = "friday") -> tuple[date, date]:
    normalized = week_start_name.lower()
    if normalized not in WEEKDAYS:
        raise ValueError(f"Unsupported week start: {week_start_name}")
    target_weekday = WEEKDAYS.index(normalized)
    delta = (anchor.weekday() - target_weekday) % 7
    start = anchor - timedelta(days=delta)
    return start, start + timedelta(days=6)


def detect_user_override(request: str) -> Literal["BUY", "SKIP"] | None:
    text = " ".join(request.lower().split())

    skip_patterns = (
        r"\bskip\b",
        r"\bdon't buy\b",
        r"\bdo not buy\b",
        r"\bno lottery\b",
        r"\bi decided not to buy\b",
    )
    if any(re.search(pattern, text) for pattern in skip_patterns):
        return "SKIP"

    buy_patterns = (
        r"\bbuy anyway\b",
        r"\bi want to buy\b",
        r"\bi've decided to buy\b",
        r"\bi have decided to buy\b",
        r"\bi'm going to buy\b",
        r"\bi am going to buy\b",
        r"\bgo ahead and buy\b",
    )
    if any(re.search(pattern, text) for pattern in buy_patterns):
        return "BUY"

    return None


def _participation_dates(
    anchor: date,
    week_start: date,
    week_end: date,
    facts: Iterable[KeralaLotteryFact],
    eligible_dates: Iterable[date] | None = None,
    numerology_priority: Mapping[date, tuple[int, int, int]] | None = None,
) -> tuple[date | None, date | None]:
    counts = Counter(fact.draw_date.weekday() for fact in facts)
    earliest = max(anchor, week_start)

    if eligible_dates is None:
        cursor = earliest
        candidates: list[date] = []
        while cursor <= week_end:
            candidates.append(cursor)
            cursor += timedelta(days=1)
    else:
        candidates = sorted(
            {
                candidate
                for candidate in eligible_dates
                if earliest <= candidate <= week_end
            }
        )

    if not candidates:
        return None, None

    priorities = numerology_priority or {}

    def ranking_key(day: date) -> tuple[int, int, int, int, date]:
        personal_family, exact_match, draw_family = priorities.get(day, (0, 0, 0))
        return (
            -personal_family,
            -exact_match,
            -draw_family,
            -counts.get(day.weekday(), 0),
            day,
        )

    # Official schedule decides which dates are operationally eligible. When
    # recovered Lakshmi numerology is available it now influences ordering, but
    # only through explicit selection-alignment observations -- never through a
    # claimed probability advantage. Historical weekday frequency remains a
    # final tie-breaker rather than a predictive rule.
    candidates.sort(key=ranking_key)
    preferred = candidates[0]
    backup = candidates[1] if len(candidates) > 1 else None
    return preferred, backup


def decide_weekly_participation(
    request: str,
    *,
    anchor: date,
    facts: Iterable[KeralaLotteryFact],
    week_start_name: str = "friday",
    eligible_dates: Iterable[date] | None = None,
    eligible_dates_status: str | None = None,
    numerology_priority: Mapping[date, tuple[int, int, int]] | None = None,
) -> KeralaLotteryDecision:
    fact_list = tuple(facts)
    eligible_date_list = tuple(eligible_dates) if eligible_dates is not None else None
    week_start, week_end = resolve_week(anchor, week_start_name)
    override = detect_user_override(request)

    preferred_date, backup_date = _participation_dates(
        anchor,
        week_start,
        week_end,
        fact_list,
        eligible_date_list,
        numerology_priority,
    )

    latest = max((fact.draw_date for fact in fact_list), default=None)
    in_week = [
        fact for fact in fact_list if week_start <= fact.draw_date <= week_end
    ]
    evidence = [f"{len(fact_list)} verified Kerala Lottery facts recalled"]
    if latest is not None:
        evidence.append(f"latest verified draw date: {latest.isoformat()}")
    evidence.append(
        f"{len(in_week)} verified draw facts currently fall inside the decision week"
    )
    if eligible_date_list is not None:
        scheduled_in_week = {
            candidate
            for candidate in eligible_date_list
            if max(anchor, week_start) <= candidate <= week_end
        }
        if eligible_dates_status in {"failed", "unavailable"}:
            evidence.append(
                f"official upcoming schedule collection status: {eligible_dates_status}; "
                "no participation date is trusted from unavailable schedule evidence"
            )
        else:
            evidence.append(
                f"official upcoming schedule supplies {len(scheduled_in_week)} eligible draw date(s) "
                "from today through the end of this decision week"
            )
            if eligible_dates_status == "partial":
                evidence.append(
                    "official upcoming schedule collection is partial; available dates are used with uncertainty"
                )
            if not scheduled_in_week:
                evidence.append("no listed draw date is available for participation in the remaining week")
    if numerology_priority:
        evidence.append(
            "experimental Lakshmi numerology ordering is active for eligible dates: "
            "personal-day 3/6/9 alignment, then exact birth/life-path/personal-year match, "
            "then draw-number 3/6/9 alignment; historical weekday frequency only breaks remaining ties"
        )

    if override == "BUY":
        recommendation: Literal["BUY", "SKIP"] = "BUY"
        evidence.append("user explicitly chose participation; Nokku preserved that override")
    elif override == "SKIP":
        recommendation = "SKIP"
        evidence.append("user explicitly chose to skip; Nokku preserved that override")
    else:
        # Cold-start policy: historical random outcomes alone are not a sound
        # reason to spend money. Real habitat evidence can evolve this policy.
        recommendation = "SKIP"
        evidence.append(
            "neutral default is SKIP because historical results do not create a proven future edge"
        )

    return KeralaLotteryDecision(
        recommendation=recommendation,
        week_start=week_start,
        week_end=week_end,
        preferred_date=preferred_date,
        backup_date=backup_date,
        preferred_time="before the official sales cutoff; no predictive time advantage inferred",
        evidence_summary=tuple(evidence),
        uncertainty=(
            "Lottery outcomes are random. Historical result patterns and numerology selection "
            "signals may help structure participation choices, but they do not establish that a "
            "future ticket is more likely to win."
        ),
        override=override,
    )
