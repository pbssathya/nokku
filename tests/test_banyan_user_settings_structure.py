import json

import pytest

from banyan.user_settings import (
    list_user_ids,
    load_user_preferences,
    migrate_user_settings_store,
)


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_non_object_banyan_store_root_is_not_treated_as_empty(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(path, ["not", "an", "object"])

    with pytest.raises(
        ValueError,
        match="Stored Banyan user settings must be a JSON object",
    ):
        load_user_preferences(path)


def test_non_object_users_section_is_not_treated_as_no_users(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(path, {"users": []})

    with pytest.raises(
        ValueError,
        match="Stored users setting must be a JSON object",
    ):
        list_user_ids(path)


def test_non_object_user_entry_is_not_silently_dropped(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(
        path,
        {
            "active_user": "alice",
            "users": {
                "alice": ["malformed"],
            },
        },
    )

    with pytest.raises(
        ValueError,
        match="Stored Banyan user 'alice' must be a JSON object",
    ):
        load_user_preferences(path)


def test_invalid_stored_user_id_is_not_silently_dropped(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(
        path,
        {
            "users": {
                "   ": {"timezone": "Asia/Kolkata"},
            },
        },
    )

    with pytest.raises(ValueError, match="Banyan user id cannot be empty"):
        list_user_ids(path)


def test_malformed_legacy_user_section_is_not_treated_as_absent(tmp_path):
    path = tmp_path / "user_settings.json"
    _write(path, {"user": ["malformed"]})

    with pytest.raises(
        ValueError,
        match="Stored legacy user setting must be a JSON object",
    ):
        migrate_user_settings_store(path)
