import json

from banyan.user_settings import (
    UserBirthProfile as BanyanUserBirthProfile,
    UserPreferences as BanyanUserPreferences,
)
from nokku.preferences import (
    KeralaLotteryPreferences,
    UserBirthProfile,
    UserPreferences,
    load_kerala_lottery_preferences,
    load_user_preferences,
    save_kerala_lottery_preferences,
    save_user_preferences,
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

    birth = UserBirthProfile(
        date="1969-08-12",
        time="05:23",
        location="Kannankulangara, North Paravur, Kerala",
        timezone="Asia/Kolkata",
    )
    save_user_preferences(
        UserPreferences(timezone="Asia/Kolkata", birth=birth),
        legacy_path,
    )
    save_kerala_lottery_preferences(
        KeralaLotteryPreferences(decision_week_start="sunday"),
        legacy_path,
    )

    loaded = load_user_preferences()

    assert loaded == UserPreferences(timezone="Asia/Kolkata", birth=birth)
    assert load_kerala_lottery_preferences().decision_week_start == "sunday"

    banyan_payload = json.loads(banyan_path.read_text(encoding="utf-8"))
    assert banyan_payload == {
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

    legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    assert legacy_payload["lottery"]["kerala"]["decision_week_start"] == "sunday"
