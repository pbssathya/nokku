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


def test_vimshottari_snapshot_normalizes_longitude_to_one_zodiac_cycle():
    ist = timezone(timedelta(hours=5, minutes=30))
    birth_at = datetime(1969, 8, 12, 5, 23, tzinfo=ist)
    target_at = datetime(2026, 8, 28, 12, 0, tzinfo=ist)

    canonical = vimshottari_snapshot(102.1541, birth_at, target_at)
    wrapped = vimshottari_snapshot(462.1541, birth_at, target_at)

    assert wrapped.natal_nakshatra == canonical.natal_nakshatra
    assert wrapped.natal_nakshatra_lord == canonical.natal_nakshatra_lord
    assert wrapped.mahadasha == canonical.mahadasha
    assert wrapped.antardasha == canonical.antardasha
    assert wrapped.status == canonical.status

    for wrapped_at, canonical_at in (
        (wrapped.mahadasha_start, canonical.mahadasha_start),
        (wrapped.mahadasha_end, canonical.mahadasha_end),
        (wrapped.antardasha_start, canonical.antardasha_start),
        (wrapped.antardasha_end, canonical.antardasha_end),
    ):
        assert abs(wrapped_at - canonical_at) <= timedelta(microseconds=10)


def test_vimshottari_snapshot_moves_to_next_antardasha_at_boundary():
    ist = timezone(timedelta(hours=5, minutes=30))
    birth_at = datetime(1969, 8, 12, 5, 23, tzinfo=ist)
    target_at = datetime(2026, 8, 28, 12, 0, tzinfo=ist)

    moon_moon = vimshottari_snapshot(102.1541, birth_at, target_at)
    boundary = moon_moon.antardasha_end
    moon_mars = vimshottari_snapshot(102.1541, birth_at, boundary)

    assert moon_moon.mahadasha == "Moon"
    assert moon_moon.antardasha == "Moon"
    assert moon_mars.mahadasha == "Moon"
    assert moon_mars.antardasha == "Mars"
    assert moon_mars.antardasha_start == boundary


def test_vimshottari_snapshot_moves_to_next_mahadasha_at_boundary():
    ist = timezone(timedelta(hours=5, minutes=30))
    birth_at = datetime(1969, 8, 12, 5, 23, tzinfo=ist)
    target_at = datetime(2026, 8, 28, 12, 0, tzinfo=ist)

    moon_moon = vimshottari_snapshot(102.1541, birth_at, target_at)
    boundary = moon_moon.mahadasha_end
    mars_mars = vimshottari_snapshot(102.1541, birth_at, boundary)

    assert moon_moon.mahadasha == "Moon"
    assert mars_mars.mahadasha == "Mars"
    assert mars_mars.antardasha == "Mars"
    assert mars_mars.mahadasha_start == boundary
    assert mars_mars.antardasha_start == boundary
