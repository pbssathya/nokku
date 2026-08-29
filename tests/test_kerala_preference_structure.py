import json

import pytest

from nokku.preferences import (
    KeralaLotteryPreferences,
    load_kerala_lottery_preferences,
    save_kerala_lottery_preferences,
)


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_non_object_nokku_preferences_root_is_not_treated_as_missing(tmp_path):
    path = tmp_path / "preferences.json"
    _write(path, ["malformed"])

    with pytest.raises(
        ValueError,
        match="Stored Nokku preferences must be a JSON object",
    ):
        load_kerala_lottery_preferences(path)


def test_non_object_lottery_section_is_not_treated_as_missing(tmp_path):
    path = tmp_path / "preferences.json"
    _write(path, {"lottery": ["malformed"]})

    with pytest.raises(
        ValueError,
        match="Stored lottery preferences must be a JSON object",
    ):
        load_kerala_lottery_preferences(path)


def test_non_object_kerala_section_is_not_treated_as_missing(tmp_path):
    path = tmp_path / "preferences.json"
    _write(path, {"lottery": {"kerala": ["malformed"]}})

    with pytest.raises(
        ValueError,
        match="Stored Kerala lottery preferences must be a JSON object",
    ):
        load_kerala_lottery_preferences(path)


def test_save_does_not_silently_replace_malformed_lottery_section(tmp_path):
    path = tmp_path / "preferences.json"
    original = {"lottery": ["malformed"], "other": {"keep": True}}
    _write(path, original)

    with pytest.raises(
        ValueError,
        match="Stored lottery preferences must be a JSON object",
    ):
        save_kerala_lottery_preferences(
            KeralaLotteryPreferences(decision_week_start="monday"),
            path,
        )

    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_save_does_not_silently_replace_malformed_kerala_section(tmp_path):
    path = tmp_path / "preferences.json"
    original = {
        "lottery": {"kerala": ["malformed"], "other_game": {"keep": True}},
        "other": {"keep": True},
    }
    _write(path, original)

    with pytest.raises(
        ValueError,
        match="Stored Kerala lottery preferences must be a JSON object",
    ):
        save_kerala_lottery_preferences(
            KeralaLotteryPreferences(decision_week_start="monday"),
            path,
        )

    assert json.loads(path.read_text(encoding="utf-8")) == original
