import json

import pytest

from banyan.user_settings import (
    UserBirthProfile as BanyanUserBirthProfile,
    UserPreferences as BanyanUserPreferences,
    get_active_user_id,
    list_user_ids,
    load_user_preferences as load_banyan_user_preferences,
    migrate_user_settings_store,
    save_user_preferences as save_banyan_user_preferences,
    set_active_user,
)
from nokku.preferences import (
    KeralaLotteryPreferences,
    UserBirthProfile,
    UserPreferences,
    load_kerala_lottery_preferences,
    load_user_preferences,
    save_kerala_lottery_preferences,
)


def test_nokku_user_setting_types_are_banyan_types():
    """Nokku must consume the shared Banyan user-setting model, not duplicate it."""
    assert UserBirthProfile is BanyanUserBirthProfile
    assert UserPreferences is BanyanUserPreferences


def test_legacy_user_settings_migrate_to_banyan_without_moving_lottery_preferences(
    tmp_path,
    monkeypatch,
):
    legacy_path = tmp_path / "nokku" / "preferences.json"
    banyan_path = tmp_path / "banyan" / "user_settings.json"
    monkeypatch.setenv("NOKKU_PREFERENCES_PATH", str(legacy_path))
    monkeypatch.setenv("BANYAN_USER_SETTINGS_PATH", str(banyan_path))

    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        json.dumps(
            {
                "user": {
                    "timezone": "Asia/Kolkata",
                    "birth": {
                        "date": "1969-08-12",
                        "time": "05:23",
                        "location": "Kannankulangara, North Paravur, Kerala",
                        "timezone": "Asia/Kolkata",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    save_kerala_lottery_preferences(
        KeralaLotteryPreferences(decision_week_start="sunday"),
        legacy_path,
    )

    birth = UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
        timezone="Asia/Kolkata",
    )
    loaded = load_user_preferences()

    assert loaded == UserPreferences(timezone="Asia/Kolkata", birth=birth)
    assert load_kerala_lottery_preferences().decision_week_start == "sunday"

    banyan_payload = json.loads(banyan_path.read_text(encoding="utf-8"))
    assert banyan_payload == {
        "active_user": "default",
        "users": {
            "default": {
                "timezone": "Asia/Kolkata",
                "birth": {
                    "date": "1969-08-12",
                    "time": "05:23",
                    "location": "Kannankulangara, North Paravur, Kerala",
                    "timezone": "Asia/Kolkata",
                },
            }
        },
    }

    legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    assert legacy_payload["lottery"]["kerala"]["decision_week_start"] == "sunday"


def test_existing_single_user_banyan_store_migrates_to_default_profile(tmp_path):
    path = tmp_path / "user_settings.json"
    path.write_text(
        json.dumps(
            {
                "user": {
                    "timezone": "Asia/Kolkata",
                    "birth": {
                        "date": "1969-08-12",
                        "time": "05:23",
                        "location": "Kannankulangara, North Paravur, Kerala",
                        "timezone": "Asia/Kolkata",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    migrate_user_settings_store(path)

    assert get_active_user_id(path) == "default"
    assert list_user_ids(path) == ("default",)
    assert load_banyan_user_preferences(path).birth == UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
        timezone="Asia/Kolkata",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "user" not in payload
    assert payload["active_user"] == "default"
    assert "default" in payload["users"]


def test_banyan_store_holds_multiple_users_and_switches_active_user(tmp_path):
    path = tmp_path / "user_settings.json"
    first = BanyanUserPreferences(
        timezone="Asia/Kolkata",
        birth=BanyanUserBirthProfile(
            date="1969-08-12",
            time="05:23",
            location="Kannankulangara, North Paravur, Kerala",
            timezone="Asia/Kolkata",
        ),
    )
    second = BanyanUserPreferences(
        timezone="Europe/London",
        birth=BanyanUserBirthProfile(
            date="1990-01-02",
            time="10:30",
            location="London, United Kingdom",
            timezone="Europe/London",
        ),
    )

    save_banyan_user_preferences(first, path, user_id="sathya", make_active=True)
    save_banyan_user_preferences(second, path, user_id="person_b")

    assert list_user_ids(path) == ("person_b", "sathya")
    assert get_active_user_id(path) == "sathya"
    assert load_banyan_user_preferences(path) == first
    assert load_banyan_user_preferences(path, user_id="person_b") == second

    set_active_user("person_b", path)

    assert get_active_user_id(path) == "person_b"
    assert load_banyan_user_preferences(path) == second
    assert load_banyan_user_preferences(path, user_id="sathya") == first


def test_invalid_stored_timezone_is_not_treated_as_missing(tmp_path):
    path = tmp_path / "user_settings.json"
    path.write_text(
        json.dumps(
            {
                "active_user": "default",
                "users": {
                    "default": {
                        "timezone": "Not/A-Timezone",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported IANA timezone"):
        load_banyan_user_preferences(path)


def test_incomplete_stored_birth_is_not_treated_as_missing(tmp_path):
    path = tmp_path / "user_settings.json"
    path.write_text(
        json.dumps(
            {
                "active_user": "default",
                "users": {
                    "default": {
                        "birth": {
                            "date": "1990-01-02",
                            "location": "London, United Kingdom",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Stored birth setting is incomplete"):
        load_banyan_user_preferences(path)
