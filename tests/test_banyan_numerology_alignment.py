from datetime import date

from banyan.numerology import (
    NumberNumerologyAlignment,
    align_number,
    build_cycle,
    build_profile,
    build_references,
)


BIRTH_DATE = date(1969, 8, 12)
TARGET_DATE = date(2026, 8, 25)


def test_build_references_preserves_labeled_profile_and_cycle_values():
    references = build_references(
        build_profile(BIRTH_DATE),
        build_cycle(BIRTH_DATE, TARGET_DATE),
    )

    assert tuple((item.label, item.value) for item in references) == (
        ("birth_number", 3),
        ("life_path", 9),
        ("personal_year", 3),
        ("personal_month", 2),
        ("personal_day", 9),
    )


def test_align_number_reports_only_supplied_numerology_relationships():
    references = build_references(
        build_profile(BIRTH_DATE),
        build_cycle(BIRTH_DATE, TARGET_DATE),
    )

    alignment = align_number("993369", references)

    assert isinstance(alignment, NumberNumerologyAlignment)
    assert alignment.number.original == "993369"
    assert alignment.digital_root_matches == ("birth_number", "personal_year")
    assert alignment.reference_digit_counts == ((2, 0), (3, 2), (9, 3))
    assert alignment.repeated_reference_digits == (3, 9)
    assert alignment.last_digit_matches == ("life_path", "personal_day")

    # Six occurs in the number, but it is not part of this supplied
    # profile/cycle context. Banyan must not inject a 3/6/9 heuristic.
    assert 6 not in dict(alignment.reference_digit_counts)
