from datetime import datetime, timedelta, timezone

import pytest

from nokku.lottery.kerala.astrology import (
    LAKSHMI_ASTROLOGY_CONVENTION,
    VIMSHOTTARI_SEQUENCE,
    VIMSHOTTARI_YEARS,
    vimshottari_snapshot,
)


def test_lakshmi_astrology_convention_is_explicit_and_experimental():
    convention = LAKSHMI_ASTROLOGY_CONVENTION

    assert convention.ayanamsa == "lahiri"
    assert convention.dasha_system == "vimshottari"
    assert convention.dasha_year_basis == "julian_365_25"
    assert convention.dasha_days_per_year == 365.25
    assert convention.status == "experimental"


def test_recovered_natal_moon_resolves_moon_moon_for_28_august_2026():
    ist = timezone(timedelta(hours=5, minutes=30))

    snapshot = vimshottari_snapshot(
        102.1541,  # Lahiri sidereal Moon: Cancer 12.1541° / Pushya pada 3
        datetime(1969, 8, 12, 5, 23, tzinfo=ist),
        datetime(2026, 8, 28, 12, 0, tzinfo=ist),
    )

    assert snapshot.natal_nakshatra == "Pushya"
    assert snapshot.natal_nakshatra_lord == "Saturn"
    assert snapshot.mahadasha == "Moon"
    assert snapshot.antardasha == "Moon"
    assert snapshot.status == "experimental"
    assert snapshot.mahadasha_start < datetime(2026, 8, 28, 12, 0, tzinfo=ist)
    assert snapshot.antardasha_end > datetime(2026, 8, 28, 12, 0, tzinfo=ist)


def test_vimshottari_sequence_and_years_form_120_year_cycle():
    assert VIMSHOTTARI_SEQUENCE == (
        "Ketu",
        "Venus",
        "Sun",
        "Moon",
        "Mars",
        "Rahu",
        "Jupiter",
        "Saturn",
        "Mercury",
    )

    assert sum(VIMSHOTTARI_YEARS[lord] for lord in VIMSHOTTARI_SEQUENCE) == 120


def test_vimshottari_snapshot_rejects_target_before_birth():
    ist = timezone(timedelta(hours=5, minutes=30))
    birth_at = datetime(1969, 8, 12, 5, 23, tzinfo=ist)

    with pytest.raises(ValueError, match="Target instant cannot precede birth instant"):
        vimshottari_snapshot(
            102.1541,
            birth_at,
            birth_at - timedelta(seconds=1),
        )
