"""Reusable Banyan numerology primitives.

This module contains domain-neutral arithmetic derived from a user's birth date,
a target calendar date, or a numeric value. It intentionally knows nothing
about lotteries, prize tiers, BUY/SKIP decisions, or application-specific
policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


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
