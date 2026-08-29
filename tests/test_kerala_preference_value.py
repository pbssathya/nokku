import json

import pytest

from nokku.preferences import load_kerala_lottery_preferences


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_decision_week_start_uses_friday_default(tmp_path):
    path = tmp_path / "preferences.json"
    _write(path, {"lottery": {"kerala": {}}})

    assert load_kerala_lottery_preferences(path).decision_week_start == "friday"


def test_valid_stored_decision_week_start_is_normalized(tmp_path):
    path = tmp_path / "preferences.json"
    _write(path, {"lottery": {"kerala": {"decision_week_start": "MONDAY"}}})

    assert load_kerala_lottery_preferences(path).decision_week_start == "monday"


def test_invalid_stored_decision_week_start_is_not_replaced_with_friday(tmp_path):
    path = tmp_path / "preferences.json"
    _write(path, {"lottery": {"kerala": {"decision_week_start": "funday"}}})

    with pytest.raises(ValueError, match="Unsupported stored decision week start: funday"):
        load_kerala_lottery_preferences(path)


@pytest.mark.parametrize("stored_value", [None, 3, False, ["monday"]])
def test_non_string_stored_decision_week_start_is_not_treated_as_missing(
    tmp_path,
    stored_value,
):
    path = tmp_path / "preferences.json"
    _write(path, {"lottery": {"kerala": {"decision_week_start": stored_value}}})

    with pytest.raises(
        ValueError,
        match="Stored decision week start must be a weekday name string",
    ):
        load_kerala_lottery_preferences(path)
