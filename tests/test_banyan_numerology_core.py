from datetime import date

from banyan.numerology import (
    NumerologyCycle,
    NumerologyProfile,
    build_cycle,
    build_profile,
    reduce_number,
)


BIRTH_DATE = date(1969, 8, 12)


def test_banyan_numerology_profile_is_domain_neutral():
    profile = build_profile(BIRTH_DATE)

    assert isinstance(profile, NumerologyProfile)
    assert profile.birth_date == BIRTH_DATE
    assert profile.birth_number == 3
    assert profile.life_path == 9


def test_banyan_numerology_cycle_reproduces_existing_arithmetic():
    cycle = build_cycle(BIRTH_DATE, date(2026, 8, 25))

    assert isinstance(cycle, NumerologyCycle)
    assert cycle.target_date == date(2026, 8, 25)
    assert cycle.personal_year == 3
    assert cycle.personal_month_compound == 11
    assert cycle.personal_month == 2
    assert cycle.personal_day_compound == 27
    assert cycle.personal_day == 9


def test_reduce_number_is_generic_and_reusable():
    assert reduce_number(789430) == 4
