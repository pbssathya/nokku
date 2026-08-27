"""Nokku-owned application preferences plus Banyan user-setting compatibility.

Common user-owned settings live at the Banyan boundary. Nokku consumes the
active Banyan user by default and keeps only its application-specific
persistence and Kerala Lottery preference behavior here.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path

from banyan.user_settings import (
    UserBirthProfile,
    UserPreferences,
    load_user_preferences as _load_banyan_user_preferences,
    migrate_user_settings_store as _migrate_banyan_user_settings_store,
    save_user_preferences as _save_banyan_user_preferences,
    user_settings_path,
    validate_birth_profile,
    validate_timezone_name,
)
from nokku.runtime import living_memory_path


VALID_WEEK_STARTS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass(frozen=True, slots=True)
class KeralaLotteryPreferences:
    """Preferences currently needed by the Kerala Lottery living habitat."""

    decision_week_start: str = "friday"


def living_preferences_path() -> Path:
    override = os.environ.get("NOKKU_PREFERENCES_PATH")
    if override:
        path = Path(override).expanduser()
    else:
        path = living_memory_path().with_name("preferences.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_payload(target: Path) -> dict[str, object]:
    if not target.exists():
        return {}
    raw = json.loads(target.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _write_payload(target: Path, payload: dict[str, object]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _default_user_settings_target() -> Path:
    """Resolve the shared store while honoring Nokku's legacy override."""
    if os.environ.get("BANYAN_USER_SETTINGS_PATH"):
        return user_settings_path()
    if os.environ.get("NOKKU_PREFERENCES_PATH"):
        return living_preferences_path()
    return user_settings_path()


def _migrate_legacy_user_settings(target: Path) -> None:
    """Promote old single-user facts into Banyan's active multi-user store."""
    legacy = living_preferences_path()

    if target == legacy:
        if target.exists():
            _migrate_banyan_user_settings_store(target)
        return

    if not target.exists() and legacy.exists():
        legacy_preferences = _load_banyan_user_preferences(legacy)
        if legacy_preferences != UserPreferences():
            _save_banyan_user_preferences(legacy_preferences, target)

    if target.exists():
        _migrate_banyan_user_settings_store(target)


def load_user_preferences(
    path: str | Path | None = None,
    *,
    user_id: str | None = None,
) -> UserPreferences:
    """Load a Banyan user, defaulting to whichever profile is active."""
    if path is not None:
        return _load_banyan_user_preferences(path, user_id=user_id)

    target = _default_user_settings_target()
    _migrate_legacy_user_settings(target)
    return _load_banyan_user_preferences(target, user_id=user_id)


def save_user_preferences(
    preferences: UserPreferences,
    path: str | Path | None = None,
    *,
    user_id: str | None = None,
    make_active: bool = False,
) -> Path:
    """Save one Banyan user without erasing another user's stable facts."""
    if path is not None:
        return _save_banyan_user_preferences(
            preferences,
            path,
            user_id=user_id,
            make_active=make_active,
        )

    target = _default_user_settings_target()
    _migrate_legacy_user_settings(target)
    return _save_banyan_user_preferences(
        preferences,
        target,
        user_id=user_id,
        make_active=make_active,
    )


def load_kerala_lottery_preferences(
    path: str | Path | None = None,
) -> KeralaLotteryPreferences:
    target = Path(path) if path is not None else living_preferences_path()
    payload = _read_payload(target)

    lottery = payload.get("lottery")
    if not isinstance(lottery, dict):
        return KeralaLotteryPreferences()
    kerala = lottery.get("kerala")
    if not isinstance(kerala, dict):
        return KeralaLotteryPreferences()

    week_start = str(kerala.get("decision_week_start", "friday")).lower()
    if week_start not in VALID_WEEK_STARTS:
        week_start = "friday"
    return KeralaLotteryPreferences(decision_week_start=week_start)


def save_kerala_lottery_preferences(
    preferences: KeralaLotteryPreferences,
    path: str | Path | None = None,
) -> Path:
    week_start = preferences.decision_week_start.lower()
    if week_start not in VALID_WEEK_STARTS:
        raise ValueError(f"Unsupported decision week start: {week_start}")

    target = Path(path) if path is not None else living_preferences_path()
    payload = _read_payload(target)

    lottery = payload.get("lottery")
    if not isinstance(lottery, dict):
        lottery = {}
    else:
        lottery = dict(lottery)

    kerala = lottery.get("kerala")
    if not isinstance(kerala, dict):
        kerala = {}
    else:
        kerala = dict(kerala)

    kerala["decision_week_start"] = week_start
    lottery["kerala"] = kerala
    payload["lottery"] = lottery
    return _write_payload(target, payload)
