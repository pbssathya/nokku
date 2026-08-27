from datetime import datetime, timedelta, timezone

from nokku.lottery.kerala.astrology_signal import lakshmi_astrology_observation
from nokku.preferences import UserBirthProfile, UserPreferences


def test_astrology_observation_uses_explicit_birth_timezone():
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

    snapshot = lakshmi_astrology_observation(
        user_preferences=preferences,
        target_at=datetime(2026, 8, 28, 12, 0, tzinfo=ist),
    )

    assert snapshot is not None
    assert snapshot.natal_nakshatra == "Pushya"
    assert snapshot.mahadasha == "Moon"
    assert snapshot.antardasha == "Moon"
    assert snapshot.status == "experimental"


def test_astrology_observation_skips_profile_without_birth_timezone():
    preferences = UserPreferences(
        timezone="Asia/Kolkata",
        birth=UserBirthProfile(
            date="1969-08-12",
            time="05:23",
            location="Kannankulangara, North Paravur, Kerala",
        ),
    )

    snapshot = lakshmi_astrology_observation(
        user_preferences=preferences,
        target_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
    )

    assert snapshot is None


def test_astrology_observation_abstains_for_different_person():
    preferences = UserPreferences(
        timezone="Asia/Kolkata",
        birth=UserBirthProfile(
            date="1990-01-01",
            time="10:00",
            location="Kochi, Kerala",
            timezone="Asia/Kolkata",
        ),
    )

    snapshot = lakshmi_astrology_observation(
        user_preferences=preferences,
        target_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
    )

    assert snapshot is None
