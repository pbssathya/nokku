from datetime import datetime, timedelta, timezone

import pytest

from nokku.lottery.kerala.ephemeris import (
    LUNAR_NODE_CONVENTION,
    lahiri_ayanamsa_deg,
    lakshmi_transit_receipt,
    lunar_node_receipt,
    moon_phase_angle_deg,
    sidereal_position,
)


IST = timezone(timedelta(hours=5, minutes=30))
NATAL_AT = datetime(1969, 8, 12, 5, 23, tzinfo=IST)
KR_768_DRAW_AT = datetime(2026, 9, 12, 15, 0, tzinfo=IST)
NEW_MOON_AT = datetime(2026, 9, 11, 8, 57, tzinfo=IST)
SK_69_DRAW_AT = datetime(2026, 9, 11, 15, 0, tzinfo=IST)


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


def test_existing_skyfield_path_supplies_sun_without_new_dependency():
    sun = sidereal_position("sun", target_at=KR_768_DRAW_AT)

    assert sun.body == "sun"
    assert sun.status == "experimental"
    assert sun.ephemeris_kernel == "de421.bsp"
    assert sun.sign_name == "Leo"
    assert 0.0 <= sun.sidereal_longitude_deg < 360.0


def test_recovered_lakshmi_ketu_uses_osculating_true_node_convention():
    nodes = lunar_node_receipt(target_at=NATAL_AT)

    assert nodes.status == "experimental"
    assert nodes.convention == LUNAR_NODE_CONVENTION
    assert nodes.ephemeris_kernel == "de421.bsp"
    assert nodes.ketu_sign_name == "Leo"
    assert nodes.ketu_sign_index == 4
    assert nodes.rahu_tropical_longitude_deg == pytest.approx(351.392195483, abs=1e-6)
    assert nodes.ketu_sidereal_longitude_deg == pytest.approx(147.959572725, abs=1e-6)

    # Recovered Lakshmi analysis recorded natal Ketu ~ Leo 27°58′.
    recovered_ketu = 27 + 58 / 60
    error_arcmin = abs(nodes.ketu_degrees_in_sign - recovered_ketu) * 60
    assert error_arcmin < 1.0


def test_skyfield_moon_phase_reproduces_11_sep_new_moon_near_zero_angle():
    phase = moon_phase_angle_deg(target_at=NEW_MOON_AT)

    distance_from_new = min(phase, 360.0 - phase)
    assert distance_from_new < 0.25


def test_lakshmi_transit_receipt_preserves_sun_and_dark_moon_facts():
    receipt = lakshmi_transit_receipt(target_at=SK_69_DRAW_AT)

    assert receipt.sun is not None
    assert receipt.sun.body == "sun"
    assert receipt.moon_phase_angle_deg is not None
    # 3 PM IST is only a few hours after the astronomical New Moon.
    distance_from_new = min(
        receipt.moon_phase_angle_deg,
        360.0 - receipt.moon_phase_angle_deg,
    )
    assert distance_from_new < 5.0


def test_lahiri_ayanamsa_is_explicitly_anchored_at_j2000():
    assert lahiri_ayanamsa_deg(2451545.0) == pytest.approx(
        23 + 51 / 60 + 25.53 / 3600,
        abs=1e-12,
    )


def test_ephemeris_requires_timezone_aware_target():
    with pytest.raises(ValueError, match="timezone-aware"):
        sidereal_position("moon", target_at=datetime(2026, 9, 12, 15, 0))

    with pytest.raises(ValueError, match="timezone-aware"):
        moon_phase_angle_deg(target_at=datetime(2026, 9, 11, 8, 57))

    with pytest.raises(ValueError, match="timezone-aware"):
        lunar_node_receipt(target_at=datetime(1969, 8, 12, 5, 23))
