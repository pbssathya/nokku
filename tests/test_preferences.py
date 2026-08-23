from nokku.preferences import (
    KeralaLotteryPreferences,
    load_kerala_lottery_preferences,
    save_kerala_lottery_preferences,
)


def test_missing_preferences_use_friday_default(tmp_path):
    preferences = load_kerala_lottery_preferences(tmp_path / "missing.json")

    assert preferences.decision_week_start == "friday"


def test_saved_kerala_week_start_round_trips(tmp_path):
    path = tmp_path / "preferences.json"
    save_kerala_lottery_preferences(
        KeralaLotteryPreferences(decision_week_start="monday"),
        path,
    )

    assert load_kerala_lottery_preferences(path).decision_week_start == "monday"
