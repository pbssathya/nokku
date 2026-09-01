"""Mechanical structural baselines for fixed-width decimal strings.

This module derives exact combinatorial reference rates for a declared model:
each position in a fixed-width decimal string is independently and uniformly
selected from digits 0 through 9, with leading zeros allowed.

The result is a mechanical control only. It does not assert that any real-world
generating process follows this model and it knows nothing about lotteries,
numerology meaning, users, astrology, scoring, or decision policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable


ANALYSIS_CONTRACT = "banyan.decimal_structural_baseline.v1"

_SUPPORTED_METRICS = (
    "digital_root_match",
    "reference_digit_repeated",
    "last_digit_match",
)

_ASSUMPTIONS = (
    "mechanical control over the complete fixed-width decimal-string space",
    "each position is independently and uniformly selected from digits 0 through 9",
    "leading zeros are allowed and remain part of the fixed-width value",
    "the control is a mathematical reference, not an assertion about any real generating process",
)


@dataclass(frozen=True, slots=True)
class DecimalStructuralBaselineMetric:
    """Exact expected count and rate for one structural metric/reference digit."""

    metric: str
    reference_value: int
    expected_count: int
    space_size: int
    expected_rate: float


@dataclass(frozen=True, slots=True)
class DecimalStructuralBaselineAnalysis:
    """Truthful receipt for one fixed-width decimal mechanical control."""

    status: str
    contract: str
    digit_length: int
    space_size: int
    reference_values: tuple[int, ...]
    assumptions: tuple[str, ...]
    metrics: tuple[DecimalStructuralBaselineMetric, ...]
    transformations: tuple[str, ...]
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _validate_digit_length(digit_length: int) -> int:
    if (
        not isinstance(digit_length, int)
        or isinstance(digit_length, bool)
        or digit_length < 1
    ):
        raise ValueError("digit_length must be a positive integer")
    return digit_length


def _validate_reference_values(reference_values: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(reference_values)
    if not normalized:
        raise ValueError("at least one reference digit is required")

    seen: set[int] = set()
    for value in normalized:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 9:
            raise ValueError("reference digits must be integers from 0 to 9")
        if value in seen:
            raise ValueError(f"duplicate reference digit: {value}")
        seen.add(value)

    return normalized


def _rate(expected_count: int, space_size: int) -> float:
    return float(Fraction(expected_count, space_size))


def _digital_root_expected_count(*, reference_value: int, space_size: int) -> int:
    # In the complete 0..(10^n-1) fixed-width space, all-zero is the only
    # digital-root-0 value. Every non-zero residue class 1..9 occurs equally.
    if reference_value == 0:
        return 1
    return (space_size - 1) // 9


def _repeated_digit_expected_count(*, digit_length: int, space_size: int) -> int:
    # For a specified digit, subtract strings containing it zero times and
    # exactly once from the complete fixed-width decimal space.
    zero_occurrences = 9**digit_length
    exactly_one_occurrence = digit_length * 9 ** (digit_length - 1)
    return space_size - zero_occurrences - exactly_one_occurrence


def analyze_decimal_structural_baseline(
    *,
    digit_length: int,
    reference_values: Iterable[int],
) -> DecimalStructuralBaselineAnalysis:
    """Derive exact structural expectations for one fixed-width decimal space.

    Supported v1 metrics intentionally match only the structural relationships
    already consumed by ``banyan.anonymous_historical_numerology.v1``:

    * ``digital_root_match``;
    * ``reference_digit_repeated`` — the specified digit occurs at least twice;
    * ``last_digit_match``.

    The implementation uses closed-form combinatorial counts and never enumerates
    the decimal space.
    """
    length = _validate_digit_length(digit_length)
    references = _validate_reference_values(reference_values)

    space_size = 10**length
    repeated_count = _repeated_digit_expected_count(
        digit_length=length,
        space_size=space_size,
    )
    last_digit_count = space_size // 10

    metrics: list[DecimalStructuralBaselineMetric] = []
    for reference_value in references:
        root_count = _digital_root_expected_count(
            reference_value=reference_value,
            space_size=space_size,
        )

        for metric, expected_count in (
            ("digital_root_match", root_count),
            ("reference_digit_repeated", repeated_count),
            ("last_digit_match", last_digit_count),
        ):
            metrics.append(
                DecimalStructuralBaselineMetric(
                    metric=metric,
                    reference_value=reference_value,
                    expected_count=expected_count,
                    space_size=space_size,
                    expected_rate=_rate(expected_count, space_size),
                )
            )

    transformations = (
        "derived the complete fixed-width decimal space as 10 ** digit_length",
        "derived digital-root counts exactly, preserving the unique all-zero root-0 case",
        "derived repeated-reference-digit counts by complementing zero and exactly-one occurrences",
        "derived last-digit counts exactly from the ten equiprobable final digits",
        "used closed-form combinatorial counts without enumerating the decimal space",
    )

    return DecimalStructuralBaselineAnalysis(
        status="success",
        contract=ANALYSIS_CONTRACT,
        digit_length=length,
        space_size=space_size,
        reference_values=references,
        assumptions=_ASSUMPTIONS,
        metrics=tuple(metrics),
        transformations=transformations,
    )
