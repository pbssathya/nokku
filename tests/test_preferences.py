import json

import pytest

from nokku.preferences import (
    KeralaLotteryPreferences,
    UserBirthProfile,
    UserPreferences,
    load_kerala_lottery_preferences,
    load_user_preferences,
    save_kerala_lottery_preferences,
    save_user_preferences,
)


def test_missing_preferences_use_friday_default(tmp_path):
    preferences = load_kerala_lottery_preferences(tmp_path / "missing.json")

    assert preferences.decision_week_start == "friday"


def test_missing_user_preferences_have_no_timezone_or_birth_profile(tmp_path):
    preferences = load_user_preferences(tmp_path / "missing.json")

    assert preferences.timezone is None
    assert preferences.birth is None


def test_saved_kerala_week_start_round_trips(tmp_path):
    path = tmp_path / "preferences.json"
    save_kerala_lottery_preferences(
        KeralaLotteryPreferences(decision_week_start="monday"),
        path,
    )

    assert load_kerala_lottery_preferences(path).decision_week_start == "monday"


def test_saved_user_timezone_round_trips(tmp_path):
    path = tmp_path / "preferences.json"
    save_user_preferences(UserPreferences(timezone="Europe/London"), path)

    assert load_user_preferences(path).timezone == "Europe/London"


def test_saved_user_birth_profile_round_trips(tmp_path):
    path = tmp_path / "preferences.json"
    birth = UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
    )
    save_user_preferences(
        UserPreferences(timezone="Asia/Kolkata", birth=birth),
        path,
    )

    loaded = load_user_preferences(path)
    assert loaded.timezone == "Asia/Kolkata"
    assert loaded.birth == birth


def test_saved_birth_timezone_round_trips_independently_of_user_timezone(tmp_path):
    path = tmp_path / "preferences.json"
    birth = UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
        timezone="Asia/Kolkata",
    )
    save_user_preferences(
        UserPreferences(timezone="Europe/London", birth=birth),
        path,
    )

    loaded = load_user_preferences(path)
    assert loaded.timezone == "Europe/London"
    assert loaded.birth == birth
    assert loaded.birth.timezone == "Asia/Kolkata"


def test_birth_profile_builds_aware_datetime_only_with_birth_timezone():
    zoned = UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
        timezone="Asia/Kolkata",
    )
    unzoned = UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
    )

    birth_at = zoned.as_aware_datetime()

    assert birth_at is not None
    assert birth_at.isoformat() == "1969-08-12T05:23:00+05:30"
    assert unzoned.as_aware_datetime() is None


def test_partial_user_preference_write_preserves_existing_birth_profile(tmp_path):
    path = tmp_path / "preferences.json"
    birth = UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
    )
    save_user_preferences(
        UserPreferences(timezone="Asia/Kolkata", birth=birth),
        path,
    )

    save_user_preferences(UserPreferences(timezone="Europe/London"), path)

    loaded = load_user_preferences(path)
    assert loaded.timezone == "Europe/London"
    assert loaded.birth == birth


def test_preference_writes_preserve_other_sections(tmp_path):
    path = tmp_path / "preferences.json"
    birth = UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
    )
    save_user_preferences(
        UserPreferences(timezone="Asia/Kolkata", birth=birth),
        path,
    )
    save_kerala_lottery_preferences(
        KeralaLotteryPreferences(decision_week_start="monday"),
        path,
    )
    save_user_preferences(UserPreferences(timezone="Europe/London"), path)

    loaded = load_user_preferences(path)
    assert loaded.timezone == "Europe/London"
    assert loaded.birth == birth
    assert load_kerala_lottery_preferences(path).decision_week_start == "monday"

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "users": {
            "default": {
                "timezone": "Europe/London",
                "birth": {
                    "date": "1969-08-12",
                    "time": "05:23",
                    "location": "Kannankulangara, North Paravur, Kerala",
                },
            }
        },
        "active_user": "default",
        "lottery": {"kerala": {"decision_week_start": "monday"}},
    }


def test_invalid_user_timezone_is_rejected_when_saving(tmp_path):
    with pytest.raises(ValueError, match="Unsupported IANA timezone"):
        save_user_preferences(
            UserPreferences(timezone="Not/A_Timezone"),
            tmp_path / "preferences.json",
        )


def test_invalid_birth_profile_is_rejected_when_saving(tmp_path):
    with pytest.raises(ValueError, match="Birth date must be YYYY-MM-DD"):
        save_user_preferences(
            UserPreferences(
                birth=UserBirthProfile(
                    date="12/08/1969",
                    time="05:23",
                    location="Kannankulangara, North Paravur, Kerala",
                )
            ),
            tmp_path / "preferences.json",
        )
