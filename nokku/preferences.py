"""Nokku-owned application preferences plus Banyan user-setting compatibility.

Common user-owned settings live at the Banyan boundary. Nokku keeps only its
application-specific persistence and Kerala Lottery preference behavior here.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path

from banyan.user_settings import (
    UserBirthProfile,
    UserPreferences,
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


def _load_birth_profile(user: dict[str, object]) -> UserBirthProfile | None:
    raw_birth = user.get("birth")
    if not isinstance(raw_birth, dict):
        return None
    raw_date = raw_birth.get("date")
    raw_time = raw_birth.get("time")
    raw_location = raw_birth.get("location")
    if raw_date is None or raw_time is None or raw_location is None:
        return None
    raw_timezone = raw_birth.get("timezone")
    try:
        return validate_birth_profile(
            UserBirthProfile(
                date=str(raw_date),
                time=str(raw_time),
                location=str(raw_location),
                timezone=str(raw_timezone) if raw_timezone is not None else None,
            )
        )
    except ValueError:
        return None


def load_user_preferences(path: str | Path | None = None) -> UserPreferences:
    """Load Banyan user settings from Nokku's current compatibility store."""
    target = Path(path) if path is not None else living_preferences_path()
    payload = _read_payload(target)
    user = payload.get("user")
    if not isinstance(user, dict):
        return UserPreferences()

    timezone_name: str | None = None
    raw_timezone = user.get("timezone")
    if raw_timezone is not None:
        try:
            timezone_name = validate_timezone_name(str(raw_timezone))
        except ValueError:
            timezone_name = None

    return UserPreferences(
        timezone=timezone_name,
        birth=_load_birth_profile(user),
    )


def save_user_preferences(
    preferences: UserPreferences,
    path: str | Path | None = None,
) -> Path:
    """Merge Banyan user settings into Nokku's current compatibility store.

    ``None`` means "not supplied" here, so an unrelated settings write cannot
    silently erase another stable user-owned field.
    """
    target = Path(path) if path is not None else living_preferences_path()
    payload = _read_payload(target)

    user = payload.get("user")
    if not isinstance(user, dict):
        user = {}
    else:
        user = dict(user)

    if preferences.timezone is not None:
        user["timezone"] = validate_timezone_name(preferences.timezone)

    if preferences.birth is not None:
        birth = validate_birth_profile(preferences.birth)
        birth_payload: dict[str, object] = {
            "date": birth.date,
            "time": birth.time,
            "location": birth.location,
        }
        if birth.timezone is not None:
            birth_payload["timezone"] = birth.timezone
        user["birth"] = birth_payload

    payload["user"] = user
    return _write_payload(target, payload)


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
