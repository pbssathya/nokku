"""Recovered Project Lakshmi numerology signals for Kerala Lottery.

This module encodes only arithmetic that is reproducible from a preserved
Lakshmi weekly analysis. It does not assign BUY/SKIP decisions, probabilities,
or framework-strength scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


LAKSHMI_FAMILY = frozenset({3, 6, 9})


def reduce_number(value: int) -> int:
    """Reduce a non-negative integer to one decimal digit."""
    if value < 0:
        raise ValueError("Numerology values must be non-negative")

    while value >= 10:
        value = sum(int(digit) for digit in str(value))
    return value


def birth_number(birth_date: date) -> int:
    """Lakshmi birth number: reduce the calendar day of birth."""
    return reduce_number(birth_date.day)


def life_path_number(birth_date: date) -> int:
    """Lakshmi life path: reduce all digits of the full birth date."""
    digits = f"{birth_date.year:04d}{birth_date.month:02d}{birth_date.day:02d}"
    return reduce_number(sum(int(digit) for digit in digits))


def universal_year_number(year: int) -> int:
    """Reduce the digits of a calendar year."""
    if year < 1:
        raise ValueError("year must be positive")
    return reduce_number(sum(int(digit) for digit in str(year)))


def personal_year_number(birth_date: date, year: int) -> int:
    """Recovered Lakshmi personal-year arithmetic.

    Example from the preserved 2026 analysis:
    August birth month 8 + birth number 3 + universal year 1 = 12 -> 3.
    """
    return reduce_number(
        birth_date.month
        + birth_number(birth_date)
        + universal_year_number(year)
    )


def personal_month_values(birth_date: date, target: date) -> tuple[int, int]:
    """Return the compound and reduced Lakshmi personal-month values."""
    compound = personal_year_number(birth_date, target.year) + target.month
    return compound, reduce_number(compound)


def personal_day_values(birth_date: date, target: date) -> tuple[int, int]:
    """Return the compound and reduced Lakshmi personal-day values."""
    _, month_reduced = personal_month_values(birth_date, target)
    compound = month_reduced + target.day
    return compound, reduce_number(compound)


def draw_number_reduction(draw_number: int | str) -> int:
    """Reduce the numeric draw code, e.g. 534 -> 3."""
    text = str(draw_number).strip()
    if not text or not text.isdigit():
        raise ValueError(f"Draw number must contain digits only: {draw_number!r}")
    return reduce_number(sum(int(digit) for digit in text))


@dataclass(frozen=True, slots=True)
class LakshmiNumerologySignal:
    """Explainable numerology observations for one candidate draw date."""

    target_date: date
    birth_number: int
    life_path: int
    personal_year: int
    personal_month_compound: int
    personal_month: int
    personal_day_compound: int
    personal_day: int
    draw_number: str | None = None
    draw_reduction: int | None = None

    @property
    def personal_day_in_369_family(self) -> bool:
        return self.personal_day in LAKSHMI_FAMILY

    @property
    def draw_in_369_family(self) -> bool:
        return self.draw_reduction in LAKSHMI_FAMILY

    @property
    def personal_day_matches_birth_number(self) -> bool:
        return self.personal_day == self.birth_number

    @property
    def personal_day_matches_life_path(self) -> bool:
        return self.personal_day == self.life_path

    @property
    def personal_day_matches_personal_year(self) -> bool:
        return self.personal_day == self.personal_year


def lakshmi_numerology_signal(
    *,
    birth_date: date,
    target: date,
    draw_number: int | str | None = None,
) -> LakshmiNumerologySignal:
    """Calculate only the reproducible Lakshmi numerology signal for a date."""
    month_compound, month_reduced = personal_month_values(birth_date, target)
    day_compound, day_reduced = personal_day_values(birth_date, target)
    draw_text = str(draw_number) if draw_number is not None else None
    draw_reduced = (
        draw_number_reduction(draw_number) if draw_number is not None else None
    )

    return LakshmiNumerologySignal(
        target_date=target,
        birth_number=birth_number(birth_date),
        life_path=life_path_number(birth_date),
        personal_year=personal_year_number(birth_date, target.year),
        personal_month_compound=month_compound,
        personal_month=month_reduced,
        personal_day_compound=day_compound,
        personal_day=day_reduced,
        draw_number=draw_text,
        draw_reduction=draw_reduced,
    )
