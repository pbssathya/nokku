"""Kerala Lottery numerology adapter over the reusable Banyan core.

Banyan owns the domain-neutral numerology arithmetic. This module keeps the
existing Nokku/Lakshmi public contract and adds only lottery-specific context
such as draw-number reduction and the current Lakshmi 3/6/9 observations.
It does not assign BUY/SKIP decisions, probabilities, or framework-strength
scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from banyan.numerology import (
    birth_number,
    build_cycle,
    build_profile,
    life_path_number,
    personal_day_values,
    personal_month_values,
    personal_year_number,
    reduce_number,
    universal_year_number,
)


LAKSHMI_FAMILY = frozenset({3, 6, 9})


def draw_number_reduction(draw_number: int | str) -> int:
    """Reduce a numeric lottery draw code, e.g. 534 -> 3."""
    text = str(draw_number).strip()
    if not text or not text.isdigit():
        raise ValueError(f"Draw number must contain digits only: {draw_number!r}")
    return reduce_number(sum(int(digit) for digit in text))


@dataclass(frozen=True, slots=True)
class LakshmiNumerologySignal:
    """Explainable lottery-specific numerology observations for one draw date."""

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
    """Apply Nokku's lottery-specific observations to Banyan numerology values."""
    profile = build_profile(birth_date)
    cycle = build_cycle(birth_date, target)
    draw_text = str(draw_number) if draw_number is not None else None
    draw_reduced = (
        draw_number_reduction(draw_number) if draw_number is not None else None
    )

    return LakshmiNumerologySignal(
        target_date=target,
        birth_number=profile.birth_number,
        life_path=profile.life_path,
        personal_year=cycle.personal_year,
        personal_month_compound=cycle.personal_month_compound,
        personal_month=cycle.personal_month,
        personal_day_compound=cycle.personal_day_compound,
        personal_day=cycle.personal_day,
        draw_number=draw_text,
        draw_reduction=draw_reduced,
    )
