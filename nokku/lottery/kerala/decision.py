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
from typing import Iterable, Literal


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
) -> tuple[date | None, date | None]:
    counts = Counter(fact.draw_date.weekday() for fact in facts)
    cursor = max(anchor, week_start)
    candidates: list[date] = []
    while cursor <= week_end:
        candidates.append(cursor)
        cursor += timedelta(days=1)

    if not candidates:
        return None, None

    # Historical weekday frequency is used only to choose an operational date,
    # never as evidence that the user is more likely to win on that weekday.
    candidates.sort(key=lambda day: (-counts.get(day.weekday(), 0), day))
    preferred = candidates[0]
    backup = candidates[1] if len(candidates) > 1 else None
    return preferred, backup


def decide_weekly_participation(
    request: str,
    *,
    anchor: date,
    facts: Iterable[KeralaLotteryFact],
    week_start_name: str = "friday",
) -> KeralaLotteryDecision:
    fact_list = tuple(facts)
    week_start, week_end = resolve_week(anchor, week_start_name)
    override = detect_user_override(request)

    preferred_date, backup_date = _participation_dates(
        anchor,
        week_start,
        week_end,
        fact_list,
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
            "Lottery outcomes are random. Historical result patterns may be useful for "
            "habitat analysis, but they do not establish that a future ticket is more likely to win."
        ),
        override=override,
    )
