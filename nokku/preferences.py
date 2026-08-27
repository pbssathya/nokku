"""Small user-owned preferences for Nokku's living applications.

Preferences are configuration, not accumulated experience. Durable experience
continues to live in COSsse Memory. Keep this file deliberately boring until a
real use case proves that something more elaborate is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
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
class UserBirthProfile:
    """Stable user-owned birth inputs used by optional decision signals."""

    date: str
    time: str
    location: str
    timezone: str | None = None


@dataclass(frozen=True, slots=True)
class UserPreferences:
    """Global user-owned preferences shared across Nokku applications."""

    timezone: str | None = None
    birth: UserBirthProfile | None = None


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


def validate_birth_profile(profile: UserBirthProfile) -> UserBirthProfile:
    """Validate stable birth inputs without deriving astrology/numerology here."""
    birth_date = profile.date.strip()
    birth_time = profile.time.strip()
    location = " ".join(profile.location.split())
    if not location:
        raise ValueError("Birth location cannot be empty.")
    try:
        date.fromisoformat(birth_date)
    except ValueError as exc:
        raise ValueError("Birth date must be YYYY-MM-DD.") from exc
    try:
        time.fromisoformat(birth_time)
    except ValueError as exc:
        raise ValueError("Birth time must be HH:MM or HH:MM:SS.") from exc

    birth_timezone = None
    if profile.timezone is not None:
        birth_timezone = validate_timezone_name(profile.timezone)

    return UserBirthProfile(
        date=birth_date,
        time=birth_time,
        location=location,
        timezone=birth_timezone,
    )


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
    """Merge supplied user fields into durable preferences.

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
