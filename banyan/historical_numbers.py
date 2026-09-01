"""Domain-neutral descriptive analysis over historical numeric observations.

The caller supplies numeric observations, source metadata, an evidence checkpoint,
and an optional date range. This module reports structural historical facts only.
It reuses Banyan's number-observation primitive and intentionally performs no
lottery interpretation, finite-space expectation, prediction, personal
numerology, astrology, scoring, or BUY/SKIP policy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .numerology import observe_number


ANALYSIS_CONTRACT = "banyan.historical_numbers.v1"


@dataclass(frozen=True, slots=True)
class HistoricalNumberRecord:
    """One dated numeric observation supplied by any domain adapter."""

    value: int | str
    observed_on: date
    source: str = ""


@dataclass(frozen=True, slots=True)
class HistoricalEndingCount:
    """Observed frequency of one suffix within one numeric-length population."""

    width: int
    ending: str
    observed_count: int
    sample_size: int
    observed_rate: float


@dataclass(frozen=True, slots=True)
class HistoricalExactRecurrence:
    """One exact value observed more than once in the selected population."""

    value: str
    occurrence_count: int
    first_seen: date
    last_seen: date


@dataclass(frozen=True, slots=True)
class HistoricalNumberLengthSummary:
    """Descriptive facts for one numeric length, never mixed with other lengths."""

    digit_length: int
    sample_size: int
    digital_root_counts: tuple[tuple[int, int], ...]
    ending_counts: tuple[HistoricalEndingCount, ...]
    repeated_digit_counts: tuple[tuple[int, int], ...]
    exact_recurrences: tuple[HistoricalExactRecurrence, ...]


@dataclass(frozen=True, slots=True)
class HistoricalNumberAnalysis:
    """Truthful lineage-preserving receipt for historical number structure."""

    status: str
    contract: str
    evidence_checkpoint: str
    requested_start: date | None
    requested_end: date | None
    effective_start: date | None
    effective_end: date | None
    ending_widths: tuple[int, ...]
    input_record_count: int
    selected_record_count: int
    analyzed_record_count: int
    excluded_by_range_count: int
    length_summaries: tuple[HistoricalNumberLengthSummary, ...]
    transformations: tuple[str, ...]
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _normalize_ending_widths(widths: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(widths)
    if any(not isinstance(width, int) or isinstance(width, bool) or width < 1 for width in normalized):
        raise ValueError("ending widths must be positive integers")
    if len(set(normalized)) != len(normalized):
        raise ValueError("ending widths must not contain duplicates")
    return tuple(sorted(normalized))


def analyze_historical_numbers(
    records: Iterable[HistoricalNumberRecord],
    *,
    evidence_checkpoint: str,
    start: date | None = None,
    end: date | None = None,
    ending_widths: Iterable[int] = (),
) -> HistoricalNumberAnalysis:
    """Describe historical numeric structure inside a caller-selected date range.

    Numeric lengths are always summarized separately. Suffix widths are supplied
    explicitly because useful suffix populations are domain-dependent. Widths
    larger than a particular number length are simply not applied to that length.
    Exact recurrence here is descriptive only; finite-space expected recurrence
    belongs to :mod:`banyan.recurrence`.
    """
    if not evidence_checkpoint.strip():
        raise ValueError("evidence_checkpoint must not be empty")
    if start is not None and end is not None and start > end:
        raise ValueError("start must be on or before end")

    widths = _normalize_ending_widths(ending_widths)
    normalized = tuple(records)
    selected = tuple(
        record
        for record in normalized
        if (start is None or record.observed_on >= start)
        and (end is None or record.observed_on <= end)
    )

    failures: list[str] = []
    uncertainty: list[str] = []
    observations_by_length: dict[
        int,
        list[tuple[HistoricalNumberRecord, object]],
    ] = {}

    for index, record in enumerate(selected):
        try:
            observation = observe_number(record.value)
        except ValueError as exc:
            source = record.source.strip() or f"record_index={index}"
            failures.append(
                f"historical number could not be analyzed: source={source}, "
                f"value={record.value!r}: {exc}"
            )
            continue

        observations_by_length.setdefault(len(observation.original), []).append(
            (record, observation)
        )

    summaries: list[HistoricalNumberLengthSummary] = []
    analyzed_dates: list[date] = []

    for digit_length in sorted(observations_by_length):
        items = observations_by_length[digit_length]
        sample_size = len(items)
        root_counts: Counter[int] = Counter()
        repeated_digit_counts: Counter[int] = Counter()
        ending_counters: dict[int, Counter[str]] = {
            width: Counter() for width in widths if width <= digit_length
        }
        recurrence_dates: dict[str, list[date]] = {}

        for record, observation in items:
            analyzed_dates.append(record.observed_on)
            root_counts[observation.digital_root] += 1
            for digit in observation.repeated_digits:
                repeated_digit_counts[digit] += 1
            for width, counter in ending_counters.items():
                counter[observation.original[-width:]] += 1
            recurrence_dates.setdefault(observation.original, []).append(
                record.observed_on
            )

        ending_counts = tuple(
            HistoricalEndingCount(
                width=width,
                ending=ending,
                observed_count=count,
                sample_size=sample_size,
                observed_rate=count / sample_size if sample_size else 0.0,
            )
            for width in sorted(ending_counters)
            for ending, count in sorted(ending_counters[width].items())
        )
        recurrences = tuple(
            HistoricalExactRecurrence(
                value=value,
                occurrence_count=len(dates),
                first_seen=min(dates),
                last_seen=max(dates),
            )
            for value, dates in sorted(recurrence_dates.items())
            if len(dates) > 1
        )

        summaries.append(
            HistoricalNumberLengthSummary(
                digit_length=digit_length,
                sample_size=sample_size,
                digital_root_counts=tuple(sorted(root_counts.items())),
                ending_counts=ending_counts,
                repeated_digit_counts=tuple(sorted(repeated_digit_counts.items())),
                exact_recurrences=recurrences,
            )
        )

    analyzed_count = sum(summary.sample_size for summary in summaries)
    excluded_count = len(normalized) - len(selected)
    transformations = (
        "selected records inside the caller-supplied inclusive date range",
        "reused banyan.numerology.observe_number for digits-only structural observations",
        "partitioned analyzed observations by numeric length before aggregation",
        "calculated only caller-supplied suffix widths that fit each numeric length",
        "reported exact recurrence descriptively without finite-space expectation or prediction",
    )

    if selected and not analyzed_count:
        uncertainty.append("selected range contains no analyzable numeric observations")

    status = "partial" if failures or uncertainty else "success"
    return HistoricalNumberAnalysis(
        status=status,
        contract=ANALYSIS_CONTRACT,
        evidence_checkpoint=evidence_checkpoint.strip(),
        requested_start=start,
        requested_end=end,
        effective_start=min(analyzed_dates) if analyzed_dates else None,
        effective_end=max(analyzed_dates) if analyzed_dates else None,
        ending_widths=widths,
        input_record_count=len(normalized),
        selected_record_count=len(selected),
        analyzed_record_count=analyzed_count,
        excluded_by_range_count=excluded_count,
        length_summaries=tuple(summaries),
        transformations=transformations,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )
