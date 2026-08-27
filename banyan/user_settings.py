"""Application-neutral user-owned settings for the Banyan tree.

These are stable facts/preferences owned by the user and reusable by any Banyan
application or capability. Derived numerology, astrology, and application
experience do not belong here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True, slots=True)
class UserBirthProfile:
    """Stable user-owned birth inputs shared across Banyan capabilities."""

    date: str
    time: str
    location: str
    timezone: str | None = None

    def as_aware_datetime(self) -> datetime | None:
        """Return the local birth instant when its timezone is explicitly known."""
        if self.timezone is None:
            return None
        return datetime.combine(
            date.fromisoformat(self.date),
            time.fromisoformat(self.time),
            tzinfo=ZoneInfo(self.timezone),
        )


@dataclass(frozen=True, slots=True)
class UserPreferences:
    """Common user-owned settings available to the whole Banyan tree."""

    timezone: str | None = None
    birth: UserBirthProfile | None = None


def user_settings_path() -> Path:
    """Return the Banyan-owned persistent path for common user settings."""
    override = os.environ.get("BANYAN_USER_SETTINGS_PATH")
    if override:
        path = Path(override).expanduser()
    elif Path("/workspaces").exists():
        path = Path("/workspaces/.banyan/user_settings.json")
    else:
        path = Path.home() / ".local" / "share" / "banyan" / "user_settings.json"

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
    """Validate stable birth inputs without deriving capability-specific values."""
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
    """Load common user settings from the Banyan-owned store."""
    target = Path(path) if path is not None else user_settings_path()
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
    """Merge supplied common user fields into the Banyan-owned store.

    ``None`` means "not supplied" here, so an unrelated settings write cannot
    silently erase another stable user-owned field. When an explicit path is
    supplied, unrelated JSON sections are preserved for compatibility.
    """
    target = Path(path) if path is not None else user_settings_path()
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
