"""Descriptive recurrence and prizing observations over Kerala winning patterns.

This layer consumes the unique draw-level numeric-pattern population and reuses
Banyan's domain-neutral number observation capability. It reports recurrence,
root, ending, repeated-digit, lottery-code, and canonical prize-tier counts with
sample sizes. It intentionally performs no scoring, prediction, probability
claim, astrology, personal numerology, or BUY/SKIP policy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from banyan.numerology import observe_number

from .winning_patterns import WinningNumberPattern


@dataclass(frozen=True, slots=True)
class EndingCount:
    """Observed frequency of one suffix width/value in the analyzed population."""

    width: int
    ending: str
    observed_count: int
    sample_size: int
    observed_rate: float


@dataclass(frozen=True, slots=True)
class ExactNumberRecurrence:
    """One numeric part observed in more than one distinct draw-level pattern."""

    numeric_part: str
    occurrence_count: int
    first_seen: date
    last_seen: date


@dataclass(frozen=True, slots=True)
class HistoricalPatternAnalysisResult:
    """Truthful receipt for anonymous historical recurrence observations."""

    status: str
    sample_size: int
    analyzed_sample_size: int
    digital_root_counts: tuple[tuple[int, int], ...]
    ending_counts: tuple[EndingCount, ...]
    repeated_digit_counts: tuple[tuple[int, int], ...]
    exact_number_recurrences: tuple[ExactNumberRecurrence, ...]
    lottery_code_counts: tuple[tuple[str, int], ...]
    prize_tier_counts: tuple[tuple[str, int], ...]
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def analyze_historical_patterns(
    patterns: Iterable[WinningNumberPattern],
) -> HistoricalPatternAnalysisResult:
    """Describe recurrence and number structure without converting it to a signal."""
    normalized = tuple(patterns)
    failures: list[str] = []
    uncertainty: list[str] = []

    root_counts: Counter[int] = Counter()
    ending_counters: dict[int, Counter[str]] = {
        1: Counter(),
        2: Counter(),
        3: Counter(),
        4: Counter(),
    }
    repeated_digit_counts: Counter[int] = Counter()
    lottery_code_counts: Counter[str] = Counter()
    prize_tier_counts: Counter[str] = Counter()
    recurrence_dates: dict[str, list[date]] = {}
    analyzed = 0

    for pattern in normalized:
        try:
            observation = observe_number(pattern.numeric_part)
        except ValueError as exc:
            failures.append(
                "winning pattern could not be analyzed: "
                f"source={pattern.source}, number={pattern.numeric_part!r}: {exc}"
            )
            continue

        analyzed += 1
        root_counts[observation.digital_root] += 1
        ending_counters[1][observation.last_digit] += 1
        ending_counters[2][observation.last_two] += 1
        ending_counters[3][observation.last_three] += 1
        ending_counters[4][observation.last_four] += 1

        for digit in observation.repeated_digits:
            repeated_digit_counts[digit] += 1

        if pattern.lottery_code:
            lottery_code_counts[pattern.lottery_code] += 1
        else:
            uncertainty.append(
                "winning pattern has no lottery code: "
                f"source={pattern.source}, number={pattern.numeric_part}"
            )

        for tier in pattern.canonical_prize_tiers:
            prize_tier_counts[tier] += 1

        recurrence_dates.setdefault(pattern.numeric_part, []).append(pattern.draw_date)

    ending_counts = tuple(
        EndingCount(
            width=width,
            ending=ending,
            observed_count=count,
            sample_size=analyzed,
            observed_rate=count / analyzed if analyzed else 0.0,
        )
        for width in sorted(ending_counters)
        for ending, count in sorted(ending_counters[width].items())
    )

    exact_recurrences = tuple(
        ExactNumberRecurrence(
            numeric_part=numeric_part,
            occurrence_count=len(dates),
            first_seen=min(dates),
            last_seen=max(dates),
        )
        for numeric_part, dates in sorted(recurrence_dates.items())
        if len(dates) > 1
    )

    if failures or uncertainty:
        status = "partial"
    else:
        status = "success"

    return HistoricalPatternAnalysisResult(
        status=status,
        sample_size=len(normalized),
        analyzed_sample_size=analyzed,
        digital_root_counts=tuple(sorted(root_counts.items())),
        ending_counts=ending_counts,
        repeated_digit_counts=tuple(sorted(repeated_digit_counts.items())),
        exact_number_recurrences=exact_recurrences,
        lottery_code_counts=tuple(sorted(lottery_code_counts.items())),
        prize_tier_counts=tuple(sorted(prize_tier_counts.items())),
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )
