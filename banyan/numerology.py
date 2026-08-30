"""Reusable Banyan numerology primitives.

This module contains domain-neutral arithmetic derived from a user's birth date,
a target calendar date, or a numeric value. It intentionally knows nothing
about lotteries, prize tiers, BUY/SKIP decisions, or application-specific
policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


def reduce_number(value: int) -> int:
    """Reduce a non-negative integer to one decimal digit."""
    if value < 0:
        raise ValueError("Numerology values must be non-negative")

    while value >= 10:
        value = sum(int(digit) for digit in str(value))
    return value


def birth_number(birth_date: date) -> int:
    """Reduce the calendar day of birth."""
    return reduce_number(birth_date.day)


def life_path_number(birth_date: date) -> int:
    """Reduce all digits of the full birth date."""
    digits = f"{birth_date.year:04d}{birth_date.month:02d}{birth_date.day:02d}"
    return reduce_number(sum(int(digit) for digit in digits))


def universal_year_number(year: int) -> int:
    """Reduce the digits of a positive calendar year."""
    if year < 1:
        raise ValueError("year must be positive")
    return reduce_number(sum(int(digit) for digit in str(year)))


def personal_year_number(birth_date: date, year: int) -> int:
    """Derive the personal-year number using the current Banyan convention."""
    return reduce_number(
        birth_date.month
        + birth_number(birth_date)
        + universal_year_number(year)
    )


def personal_month_values(birth_date: date, target: date) -> tuple[int, int]:
    """Return personal-month compound and reduced values."""
    compound = personal_year_number(birth_date, target.year) + target.month
    return compound, reduce_number(compound)


def personal_day_values(birth_date: date, target: date) -> tuple[int, int]:
    """Return personal-day compound and reduced values."""
    _, month_reduced = personal_month_values(birth_date, target)
    compound = month_reduced + target.day
    return compound, reduce_number(compound)


@dataclass(frozen=True, slots=True)
class NumerologyProfile:
    """Domain-neutral numerology values derived only from a birth date."""

    birth_date: date
    birth_number: int
    life_path: int


@dataclass(frozen=True, slots=True)
class NumerologyCycle:
    """Domain-neutral personal-cycle values for one target date."""

    target_date: date
    personal_year: int
    personal_month_compound: int
    personal_month: int
    personal_day_compound: int
    personal_day: int


@dataclass(frozen=True, slots=True)
class NumberPatternObservation:
    """Domain-neutral structural observation of one digits-only value."""

    original: str
    digits: tuple[int, ...]
    digit_sum: int
    digital_root: int
    last_digit: str
    last_two: str
    last_three: str
    last_four: str
    digit_frequency: tuple[int, ...]
    repeated_digits: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class NumerologyReference:
    """One labeled reduced numerology value supplied to an analysis."""

    label: str
    value: int


@dataclass(frozen=True, slots=True)
class NumberNumerologyAlignment:
    """Truthful relationships between one number and supplied references."""

    number: NumberPatternObservation
    references: tuple[NumerologyReference, ...]
    digital_root_matches: tuple[str, ...]
    reference_digit_counts: tuple[tuple[int, int], ...]
    repeated_reference_digits: tuple[int, ...]
    last_digit_matches: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HistoricalNumerologySample:
    """One historical number with caller-supplied references and optional group."""

    value: int | str
    references: tuple[NumerologyReference, ...]
    group: str | None = None


@dataclass(frozen=True, slots=True)
class BaselineRate:
    """Explicit caller-supplied expected rate for one historical metric."""

    metric: str
    reference_label: str
    expected_rate: float
    group: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalMetric:
    """Observed count/rate plus an optional explicit comparison baseline."""

    metric: str
    reference_label: str
    observed_count: int
    sample_size: int
    observed_rate: float
    baseline_rate: float | None
    delta_from_baseline: float | None


@dataclass(frozen=True, slots=True)
class HistoricalGroupSummary:
    """Historical numerology metrics for one caller-defined group."""

    group: str
    sample_size: int
    metrics: tuple[HistoricalMetric, ...]


@dataclass(frozen=True, slots=True)
class HistoricalNumerologySummary:
    """Domain-neutral historical numerology aggregation receipt."""

    sample_size: int
    metrics: tuple[HistoricalMetric, ...]
    groups: tuple[HistoricalGroupSummary, ...]


def build_profile(birth_date: date) -> NumerologyProfile:
    """Build the reusable numerology profile for a birth date."""
    return NumerologyProfile(
        birth_date=birth_date,
        birth_number=birth_number(birth_date),
        life_path=life_path_number(birth_date),
    )


def build_cycle(birth_date: date, target: date) -> NumerologyCycle:
    """Build the reusable personal-cycle observation for a target date."""
    month_compound, month_reduced = personal_month_values(birth_date, target)
    day_compound, day_reduced = personal_day_values(birth_date, target)
    return NumerologyCycle(
        target_date=target,
        personal_year=personal_year_number(birth_date, target.year),
        personal_month_compound=month_compound,
        personal_month=month_reduced,
        personal_day_compound=day_compound,
        personal_day=day_reduced,
    )


def observe_number(value: int | str) -> NumberPatternObservation:
    """Describe the digit structure of a numeric value without domain semantics."""
    text = str(value).strip()
    if not text or not text.isdigit():
        raise ValueError(f"Numerology number observations require digits only: {value!r}")

    digits = tuple(int(digit) for digit in text)
    digit_sum = sum(digits)
    frequency = tuple(digits.count(digit) for digit in range(10))

    return NumberPatternObservation(
        original=text,
        digits=digits,
        digit_sum=digit_sum,
        digital_root=reduce_number(digit_sum),
        last_digit=text[-1:],
        last_two=text[-2:],
        last_three=text[-3:],
        last_four=text[-4:],
        digit_frequency=frequency,
        repeated_digits=tuple(
            digit for digit, count in enumerate(frequency) if count > 1
        ),
    )


def build_references(
    profile: NumerologyProfile,
    cycle: NumerologyCycle,
) -> tuple[NumerologyReference, ...]:
    """Build labeled references from the current Banyan profile/cycle convention."""
    return (
        NumerologyReference("birth_number", profile.birth_number),
        NumerologyReference("life_path", profile.life_path),
        NumerologyReference("personal_year", cycle.personal_year),
        NumerologyReference("personal_month", cycle.personal_month),
        NumerologyReference("personal_day", cycle.personal_day),
    )


def _validated_references(
    references: Iterable[NumerologyReference],
) -> tuple[NumerologyReference, ...]:
    normalized = tuple(references)
    for reference in normalized:
        if not reference.label.strip():
            raise ValueError("Numerology reference labels must not be empty")
        if reference.value < 0 or reference.value > 9:
            raise ValueError(
                "Numerology alignment references must be reduced digits from 0 to 9"
            )
    return normalized


def align_number(
    value: int | str,
    references: Iterable[NumerologyReference],
) -> NumberNumerologyAlignment:
    """Compare one number only with the explicitly supplied numerology references."""
    number = observe_number(value)
    normalized = _validated_references(references)
    reference_digits = tuple(sorted({item.value for item in normalized}))
    reference_digit_counts = tuple(
        (digit, number.digit_frequency[digit]) for digit in reference_digits
    )

    return NumberNumerologyAlignment(
        number=number,
        references=normalized,
        digital_root_matches=tuple(
            item.label
            for item in normalized
            if item.value == number.digital_root
        ),
        reference_digit_counts=reference_digit_counts,
        repeated_reference_digits=tuple(
            digit for digit, count in reference_digit_counts if count > 1
        ),
        last_digit_matches=tuple(
            item.label
            for item in normalized
            if item.value == int(number.last_digit)
        ),
    )


_HISTORICAL_METRICS = (
    "digital_root_match",
    "reference_digit_present",
    "reference_digit_repeated",
    "last_digit_match",
)


def _validate_baselines(
    baselines: Iterable[BaselineRate],
) -> dict[tuple[str | None, str, str], float]:
    result: dict[tuple[str | None, str, str], float] = {}
    for baseline in baselines:
        if baseline.metric not in _HISTORICAL_METRICS:
            raise ValueError(f"Unsupported historical numerology metric: {baseline.metric}")
        if not baseline.reference_label.strip():
            raise ValueError("Baseline reference labels must not be empty")
        if baseline.expected_rate < 0 or baseline.expected_rate > 1:
            raise ValueError("Baseline expected_rate must be between 0 and 1")
        key = (baseline.group, baseline.metric, baseline.reference_label)
        if key in result:
            raise ValueError(f"Duplicate baseline supplied for {key!r}")
        result[key] = baseline.expected_rate
    return result


def _historical_metrics_for_samples(
    samples: tuple[HistoricalNumerologySample, ...],
    *,
    baseline_lookup: dict[tuple[str | None, str, str], float],
    group: str | None,
) -> tuple[HistoricalMetric, ...]:
    counters: dict[tuple[str, str], list[int]] = {}

    for sample in samples:
        alignment = align_number(sample.value, sample.references)
        label_values: dict[str, int] = {
            reference.label: reference.value for reference in alignment.references
        }
        digit_counts = dict(alignment.reference_digit_counts)
        digital_root_matches = set(alignment.digital_root_matches)
        last_digit_matches = set(alignment.last_digit_matches)

        for label, value in label_values.items():
            outcomes = {
                "digital_root_match": label in digital_root_matches,
                "reference_digit_present": digit_counts.get(value, 0) > 0,
                "reference_digit_repeated": digit_counts.get(value, 0) > 1,
                "last_digit_match": label in last_digit_matches,
            }
            for metric, matched in outcomes.items():
                counter = counters.setdefault((metric, label), [0, 0])
                counter[1] += 1
                if matched:
                    counter[0] += 1

    metrics: list[HistoricalMetric] = []
    for (metric, label), (observed_count, sample_size) in sorted(counters.items()):
        observed_rate = observed_count / sample_size if sample_size else 0.0
        baseline_rate = baseline_lookup.get((group, metric, label))
        metrics.append(
            HistoricalMetric(
                metric=metric,
                reference_label=label,
                observed_count=observed_count,
                sample_size=sample_size,
                observed_rate=observed_rate,
                baseline_rate=baseline_rate,
                delta_from_baseline=(
                    observed_rate - baseline_rate
                    if baseline_rate is not None
                    else None
                ),
            )
        )
    return tuple(metrics)


def analyze_history(
    samples: Iterable[HistoricalNumerologySample],
    *,
    baselines: Iterable[BaselineRate] = (),
) -> HistoricalNumerologySummary:
    """Aggregate historical relationships without inventing a domain baseline.

    Baselines are optional and must be supplied explicitly by the caller because
    expected rates depend on the domain's number-generating process. The analyzer
    reports observed counts/rates whether or not a baseline is available.
    """
    normalized_samples = tuple(samples)
    baseline_lookup = _validate_baselines(baselines)

    overall_metrics = _historical_metrics_for_samples(
        normalized_samples,
        baseline_lookup=baseline_lookup,
        group=None,
    )

    named_groups = sorted(
        {sample.group for sample in normalized_samples if sample.group is not None}
    )
    group_summaries = tuple(
        HistoricalGroupSummary(
            group=group,
            sample_size=len(
                tuple(sample for sample in normalized_samples if sample.group == group)
            ),
            metrics=_historical_metrics_for_samples(
                tuple(sample for sample in normalized_samples if sample.group == group),
                baseline_lookup=baseline_lookup,
                group=group,
            ),
        )
        for group in named_groups
    )

    return HistoricalNumerologySummary(
        sample_size=len(normalized_samples),
        metrics=overall_metrics,
        groups=group_summaries,
    )
