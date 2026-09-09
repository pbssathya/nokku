from datetime import datetime, timedelta, timezone

import pytest

from nokku.lottery.kerala.ephemeris import (
    lahiri_ayanamsa_deg,
    sidereal_position,
)


IST = timezone(timedelta(hours=5, minutes=30))
KR_768_DRAW_AT = datetime(2026, 9, 12, 15, 0, tzinfo=IST)


def test_lahiri_ephemeris_reproduces_recovered_12_sep_moon_observation():
    moon = sidereal_position("moon", target_at=KR_768_DRAW_AT)

    assert moon.status == "experimental"
    assert moon.ephemeris_kernel == "de421.bsp"
    assert moon.sign_name == "Virgo"
    assert moon.sign_index == 5
    assert moon.ayanamsa_deg == pytest.approx(24.230033712, abs=1e-6)
    assert moon.tropical_longitude_deg == pytest.approx(185.388686339, abs=1e-6)
    assert moon.sidereal_longitude_deg == pytest.approx(161.158652627, abs=1e-6)
    assert moon.degrees_in_sign == pytest.approx(11.158652627, abs=1e-6)

    # Recovered weekly Lakshmi analysis recorded Moon ~ Virgo 11°09′.
    recovered_degrees = 11 + 9 / 60
    error_arcmin = abs(moon.degrees_in_sign - recovered_degrees) * 60
    assert error_arcmin < 1.0


def test_lahiri_ephemeris_returns_jupiter_in_cancer_for_same_habitat_instant():
    jupiter = sidereal_position("jupiter", target_at=KR_768_DRAW_AT)

    assert jupiter.sign_name == "Cancer"
    assert jupiter.sign_index == 3
    assert jupiter.tropical_longitude_deg == pytest.approx(136.044466744, abs=1e-6)
    assert jupiter.sidereal_longitude_deg == pytest.approx(111.814433032, abs=1e-6)
    assert jupiter.degrees_in_sign == pytest.approx(21.814433032, abs=1e-6)


def test_lahiri_ayanamsa_is_explicitly_anchored_at_j2000():
    assert lahiri_ayanamsa_deg(2451545.0) == pytest.approx(
        23 + 51 / 60 + 25.53 / 3600,
        abs=1e-12,
    )


def test_ephemeris_requires_timezone_aware_target():
    with pytest.raises(ValueError, match="timezone-aware"):
        sidereal_position("moon", target_at=datetime(2026, 9, 12, 15, 0))
