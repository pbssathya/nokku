"""Small user-owned preferences for Nokku's living applications.

Preferences are configuration, not accumulated experience. Durable experience
continues to live in COSsse Memory. Keep this file deliberately boring until a
real use case proves that something more elaborate is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
class UserPreferences:
    """Global user-owned preferences shared across Nokku applications."""

    timezone: str | None = None


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


def validate_timezone_name(value: str) -> str:
    """Return a normalized IANA timezone name or raise for an invalid value."""
    timezone_name = value.strip()
    if not timezone_name:
        raise ValueError("User timezone cannot be empty.")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unsupported IANA timezone: {timezone_name}") from exc
    return timezone_name


def load_user_preferences(path: str | Path | None = None) -> UserPreferences:
    target = Path(path) if path is not None else living_preferences_path()
    payload = _read_payload(target)
    user = payload.get("user")
    if not isinstance(user, dict):
        return UserPreferences()

    raw_timezone = user.get("timezone")
    if raw_timezone is None:
        return UserPreferences()
    try:
        timezone_name = validate_timezone_name(str(raw_timezone))
    except ValueError:
        return UserPreferences()
    return UserPreferences(timezone=timezone_name)


def save_user_preferences(
    preferences: UserPreferences,
    path: str | Path | None = None,
) -> Path:
    target = Path(path) if path is not None else living_preferences_path()
    payload = _read_payload(target)

    user = payload.get("user")
    if not isinstance(user, dict):
        user = {}
    else:
        user = dict(user)

    if preferences.timezone is None:
        user.pop("timezone", None)
    else:
        user["timezone"] = validate_timezone_name(preferences.timezone)

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
