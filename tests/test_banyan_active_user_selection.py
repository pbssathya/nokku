import json

import pytest

from banyan.user_settings import (
    UserPreferences,
    get_active_user_id,
    list_user_ids,
    load_user_preferences,
    save_user_preferences,
    set_active_user,
)


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_multi_user_store_without_active_user_does_not_choose_a_profile(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(
        path,
        {
            "users": {
                "default": {"timezone": "Asia/Kolkata"},
                "person_b": {"timezone": "Europe/London"},
            }
        },
    )

    assert list_user_ids(path) == ("default", "person_b")
    assert get_active_user_id(path) is None
    assert load_user_preferences(path) == UserPreferences()


def test_single_default_profile_without_active_user_is_not_silently_selected(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(
        path,
        {
            "users": {
                "default": {"timezone": "Asia/Kolkata"},
            }
        },
    )

    assert get_active_user_id(path) is None
    assert load_user_preferences(path) == UserPreferences()


def test_explicit_set_active_user_resolves_store_with_no_active_selection(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(
        path,
        {
            "users": {
                "alice": {"timezone": "Asia/Kolkata"},
                "bob": {"timezone": "Europe/London"},
            }
        },
    )

    set_active_user("bob", path)

    assert get_active_user_id(path) == "bob"
    assert load_user_preferences(path).timezone == "Europe/London"


def test_unknown_stored_active_user_is_not_replaced_by_fallback(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(
        path,
        {
            "active_user": "ghost",
            "users": {
                "default": {"timezone": "Asia/Kolkata"},
            },
        },
    )

    with pytest.raises(
        ValueError,
        match="Stored active Banyan user 'ghost' does not exist",
    ):
        load_user_preferences(path)


def test_non_string_stored_active_user_is_not_treated_as_missing(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(
        path,
        {
            "active_user": 123,
            "users": {
                "default": {"timezone": "Asia/Kolkata"},
            },
        },
    )

    with pytest.raises(
        ValueError,
        match="Stored active_user must be a Banyan user id string",
    ):
        get_active_user_id(path)


def test_save_without_user_id_does_not_choose_existing_profile_when_no_active(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(
        path,
        {
            "users": {
                "alice": {"timezone": "Asia/Kolkata"},
                "bob": {"timezone": "Europe/London"},
            }
        },
    )

    with pytest.raises(
        ValueError,
        match="No active Banyan user is selected",
    ):
        save_user_preferences(UserPreferences(timezone="Asia/Kolkata"), path)

    assert get_active_user_id(path) is None
