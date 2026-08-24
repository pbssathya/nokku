from datetime import date

from nokku.lottery.kerala.numerology import (
    birth_number,
    lakshmi_numerology_signal,
    life_path_number,
    personal_month_values,
    personal_year_number,
)


BIRTH_DATE = date(1969, 8, 12)


def test_recovered_lakshmi_profile_numbers():
    assert birth_number(BIRTH_DATE) == 3
    assert life_path_number(BIRTH_DATE) == 9
    assert personal_year_number(BIRTH_DATE, 2026) == 3
    assert personal_month_values(BIRTH_DATE, date(2026, 8, 1)) == (11, 2)


def test_recovered_august_22_to_28_personal_day_sequence():
    observed = [
        lakshmi_numerology_signal(
            birth_date=BIRTH_DATE,
            target=date(2026, 8, day),
        ).personal_day
        for day in range(22, 29)
    ]

    assert observed == [6, 7, 8, 9, 1, 2, 3]


def test_august_25_reproduces_9_to_3_alignment():
    signal = lakshmi_numerology_signal(
        birth_date=BIRTH_DATE,
        target=date(2026, 8, 25),
        draw_number=534,
    )

    assert signal.personal_day == 9
    assert signal.personal_day_matches_life_path is True
    assert signal.draw_reduction == 3
    assert signal.personal_day_in_369_family is True
    assert signal.draw_in_369_family is True


def test_august_28_reproduces_birth_and_personal_year_alignment():
    signal = lakshmi_numerology_signal(
        birth_date=BIRTH_DATE,
        target=date(2026, 8, 28),
        draw_number=67,
    )

    assert signal.personal_day == 3
    assert signal.personal_day_matches_birth_number is True
    assert signal.personal_day_matches_personal_year is True
    assert signal.personal_day_in_369_family is True
    assert signal.draw_reduction == 4
    assert signal.draw_in_369_family is False
