from datetime import datetime, timedelta, timezone

from nokku.lottery.kerala.astrology_signal import (
    lakshmi_astrology_observation,
    lakshmi_astrology_observation_result,
)
from nokku.preferences import UserBirthProfile, UserPreferences


TEST_NATAL_MOON_LONGITUDE = 102.1541


def test_astrology_observation_uses_explicit_birth_timezone_and_moon_input():
    ist = timezone(timedelta(hours=5, minutes=30))
    preferences = UserPreferences(
        timezone="Europe/London",
        birth=UserBirthProfile(
            date="1969-08-12",
            time="05:23",
            location="Kannankulangara, North Paravur, Kerala",
            timezone="Asia/Kolkata",
        ),
    )

    result = lakshmi_astrology_observation_result(
        user_preferences=preferences,
        target_at=datetime(2026, 8, 28, 12, 0, tzinfo=ist),
        natal_moon_longitude=TEST_NATAL_MOON_LONGITUDE,
    )

    assert result.status == "success"
    assert result.failures == ()
    assert result.uncertainty == ()
    assert result.natal_moon_longitude == TEST_NATAL_MOON_LONGITUDE
    snapshot = result.observation
    assert snapshot is not None
    assert snapshot.natal_nakshatra == "Pushya"
    assert snapshot.mahadasha == "Moon"
    assert snapshot.antardasha == "Moon"
    assert snapshot.status == "experimental"


def test_astrology_observation_reports_missing_birth_timezone():
    preferences = UserPreferences(
        timezone="Asia/Kolkata",
        birth=UserBirthProfile(
            date="1969-08-12",
            time="05:23",
            location="Kannankulangara, North Paravur, Kerala",
        ),
    )

    result = lakshmi_astrology_observation_result(
        user_preferences=preferences,
        target_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        natal_moon_longitude=TEST_NATAL_MOON_LONGITUDE,
    )

    assert result.status == "abstained"
    assert result.observation is None
    assert result.failures == ("birth_timezone_missing",)


def test_astrology_observation_reports_missing_derived_moon_input():
    preferences = UserPreferences(
        timezone="Asia/Kolkata",
        birth=UserBirthProfile(
            date="1990-01-01",
            time="10:00",
            location="Kochi, Kerala",
            timezone="Asia/Kolkata",
        ),
    )

    result = lakshmi_astrology_observation_result(
        user_preferences=preferences,
        target_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
    )

    assert result.status == "abstained"
    assert result.observation is None
    assert result.failures == ()
    assert result.uncertainty == ("natal_moon_longitude_not_supplied",)


def test_compatibility_view_never_invents_a_moon_input():
    preferences = UserPreferences(
        timezone="Asia/Kolkata",
        birth=UserBirthProfile(
            date="1969-08-12",
            time="05:23",
            location="Kannankulangara, North Paravur, Kerala",
            timezone="Asia/Kolkata",
        ),
    )

    assert (
        lakshmi_astrology_observation(
            user_preferences=preferences,
            target_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        )
        is None
    )
