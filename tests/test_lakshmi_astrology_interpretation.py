from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from banyan.user_settings import UserBirthProfile, UserPreferences

from nokku.lottery.kerala.astrology_interpretation import (
    MOON_NATAL_JUPITER_CONJUNCTION_ORB_DEG,
    INTERPRETATION_METHOD,
    interpret_candidate_transit,
    natal_astrology_context,
)
from nokku.lottery.kerala.ephemeris import lakshmi_transit_receipt


IST = ZoneInfo("Asia/Kolkata")


def _recovered_lakshmi_profile() -> UserPreferences:
    return UserPreferences(
        timezone="Asia/Kolkata",
        birth=UserBirthProfile(
            date="1969-08-12",
            time="05:23",
            location="Kerala, India",
            timezone="Asia/Kolkata",
        ),
    )


def test_natal_context_is_derived_from_user_birth_facts_not_hardcoded_positions():
    context = natal_astrology_context(user_preferences=_recovered_lakshmi_profile())

    assert context.status == "success"
    assert context.failures == ()
    assert context.uncertainty == ()
    assert context.moon is not None
    assert context.jupiter is not None

    # Recovered Lakshmi observations: natal Moon ~Cancer 12°09′ and
    # natal Jupiter ~Virgo 10°57′.  The independent ephemeris path should
    # reproduce those within a small tolerance without storing either value
    # as production person-specific constants.
    assert context.moon.sign_name == "Cancer"
    assert context.moon.degrees_in_sign == pytest.approx(12.15, abs=0.10)
    assert context.jupiter.sign_name == "Virgo"
    assert context.jupiter.degrees_in_sign == pytest.approx(10.95, abs=0.10)


def test_12_sep_recovered_moon_jupiter_activation_is_explainably_supportive():
    context = natal_astrology_context(user_preferences=_recovered_lakshmi_profile())
    transit = lakshmi_transit_receipt(
        target_at=datetime(2026, 9, 12, 15, 0, tzinfo=IST)
    )

    interpretation = interpret_candidate_transit(
        transit=transit,
        natal_context=context,
    )

    assert interpretation.status == "success"
    assert interpretation.method == INTERPRETATION_METHOD
    assert interpretation.reading == "supportive"
    assert interpretation.signals == ("transit_moon_close_to_natal_jupiter",)
    assert interpretation.transit_moon_to_natal_jupiter_separation_deg is not None
    assert (
        interpretation.transit_moon_to_natal_jupiter_separation_deg
        <= MOON_NATAL_JUPITER_CONJUNCTION_ORB_DEG
    )
    assert interpretation.transit_moon_to_natal_jupiter_separation_deg == pytest.approx(
        0.20,
        abs=0.10,
    )


def test_missing_birth_profile_abstains_instead_of_borrowing_natal_values():
    context = natal_astrology_context(user_preferences=UserPreferences())
    transit = lakshmi_transit_receipt(
        target_at=datetime(2026, 9, 12, 15, 0, tzinfo=IST)
    )

    interpretation = interpret_candidate_transit(
        transit=transit,
        natal_context=context,
    )

    assert context.status == "abstained"
    assert context.failures == ("birth_profile_missing",)
    assert interpretation.status == "abstained"
    assert interpretation.reading == "unresolved"
    assert interpretation.signals == ()
    assert interpretation.transit_moon_to_natal_jupiter_separation_deg is None
