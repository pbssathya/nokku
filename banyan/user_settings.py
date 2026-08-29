"""Application-neutral user-owned settings for the Banyan tree.

These are stable facts/preferences owned by a user and reusable by any Banyan
application or capability. The store can hold multiple independent user
profiles while exposing one active user to applications by default. Derived
numerology, astrology, and application experience do not belong here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_USER_ID = "default"


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
    """Common settings belonging to one Banyan user."""

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


def validate_user_id(value: str) -> str:
    """Normalize a stable store key without inventing identity semantics."""
    user_id = value.strip()
    if not user_id:
        raise ValueError("Banyan user id cannot be empty.")
    return user_id


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
    if raw_birth is None:
        return None
    if not isinstance(raw_birth, dict):
        raise ValueError("Stored birth setting must be a JSON object.")

    required = ("date", "time", "location")
    missing = [field for field in required if raw_birth.get(field) is None]
    if missing:
        raise ValueError(
            "Stored birth setting is incomplete; missing: " + ", ".join(missing)
        )

    raw_timezone = raw_birth.get("timezone")
    return validate_birth_profile(
        UserBirthProfile(
            date=str(raw_birth["date"]),
            time=str(raw_birth["time"]),
            location=str(raw_birth["location"]),
            timezone=str(raw_timezone) if raw_timezone is not None else None,
        )
    )


def _preferences_from_payload(user: dict[str, object]) -> UserPreferences:
    timezone_name: str | None = None
    raw_timezone = user.get("timezone")
    if raw_timezone is not None:
        timezone_name = validate_timezone_name(str(raw_timezone))

    return UserPreferences(
        timezone=timezone_name,
        birth=_load_birth_profile(user),
    )


def _normalized_multi_user_payload(payload: dict[str, object]) -> dict[str, object]:
    """Return current multi-user shape while preserving unrelated sections.

    The old single-user ``user`` section is interpreted as the neutral
    ``default`` profile. This function only transforms the in-memory payload;
    callers decide when to persist the migration.
    """
    normalized = dict(payload)
    users: dict[str, object] = {}

    raw_users = normalized.get("users")
    if isinstance(raw_users, dict):
        for raw_id, raw_user in raw_users.items():
            if not isinstance(raw_user, dict):
                continue
            try:
                user_id = validate_user_id(str(raw_id))
            except ValueError:
                continue
            users[user_id] = dict(raw_user)

    legacy_user = normalized.get("user")
    if not users and isinstance(legacy_user, dict):
        users[DEFAULT_USER_ID] = dict(legacy_user)

    normalized.pop("user", None)
    normalized["users"] = users

    raw_active = normalized.get("active_user")
    if isinstance(raw_active, str) and raw_active in users:
        active_user = raw_active
    elif DEFAULT_USER_ID in users:
        active_user = DEFAULT_USER_ID
    elif users:
        active_user = sorted(users)[0]
    else:
        active_user = None

    if active_user is None:
        normalized.pop("active_user", None)
    else:
        normalized["active_user"] = active_user

    return normalized


def migrate_user_settings_store(path: str | Path | None = None) -> Path:
    """Persist the current multi-user shape without changing user facts."""
    target = Path(path) if path is not None else user_settings_path()
    payload = _read_payload(target)
    normalized = _normalized_multi_user_payload(payload)
    if normalized != payload:
        _write_payload(target, normalized)
    return target


def list_user_ids(path: str | Path | None = None) -> tuple[str, ...]:
    """Return all currently stored Banyan user ids in deterministic order."""
    target = Path(path) if path is not None else user_settings_path()
    payload = _normalized_multi_user_payload(_read_payload(target))
    users = payload.get("users")
    if not isinstance(users, dict):
        return ()
    return tuple(sorted(str(user_id) for user_id in users))


def get_active_user_id(path: str | Path | None = None) -> str | None:
    """Return the active Banyan user id, or None when no profile exists."""
    target = Path(path) if path is not None else user_settings_path()
    payload = _normalized_multi_user_payload(_read_payload(target))
    active_user = payload.get("active_user")
    return str(active_user) if active_user is not None else None


def load_user_preferences(
    path: str | Path | None = None,
    *,
    user_id: str | None = None,
) -> UserPreferences:
    """Load one user's settings, defaulting to the active Banyan user."""
    target = Path(path) if path is not None else user_settings_path()
    payload = _normalized_multi_user_payload(_read_payload(target))
    users = payload.get("users")
    if not isinstance(users, dict) or not users:
        return UserPreferences()

    if user_id is None:
        selected_id = payload.get("active_user")
        if selected_id is None:
            return UserPreferences()
        selected = str(selected_id)
    else:
        selected = validate_user_id(user_id)
        if selected not in users:
            raise KeyError(f"Unknown Banyan user: {selected}")

    raw_user = users.get(selected)
    if not isinstance(raw_user, dict):
        return UserPreferences()
    return _preferences_from_payload(raw_user)


def save_user_preferences(
    preferences: UserPreferences,
    path: str | Path | None = None,
    *,
    user_id: str | None = None,
    make_active: bool = False,
) -> Path:
    """Merge supplied common fields into one independent Banyan user profile.

    ``None`` preference fields mean "not supplied", so an unrelated settings
    write cannot silently erase another stable user-owned field. Saving a named
    user does not switch the active user unless ``make_active`` is true.
    """
    target = Path(path) if path is not None else user_settings_path()
    payload = _normalized_multi_user_payload(_read_payload(target))
    raw_users = payload.get("users")
    users = dict(raw_users) if isinstance(raw_users, dict) else {}

    active_user = payload.get("active_user")
    if user_id is not None:
        selected = validate_user_id(user_id)
    elif active_user is not None:
        selected = str(active_user)
    else:
        selected = DEFAULT_USER_ID

    raw_user = users.get(selected)
    user = dict(raw_user) if isinstance(raw_user, dict) else {}

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

    users[selected] = user
    payload["users"] = users
    if make_active or active_user is None:
        payload["active_user"] = selected

    return _write_payload(target, payload)


def set_active_user(user_id: str, path: str | Path | None = None) -> Path:
    """Select one existing Banyan profile as the active user."""
    target = Path(path) if path is not None else user_settings_path()
    payload = _normalized_multi_user_payload(_read_payload(target))
    users = payload.get("users")
    selected = validate_user_id(user_id)
    if not isinstance(users, dict) or selected not in users:
        raise KeyError(f"Unknown Banyan user: {selected}")

    payload["active_user"] = selected
    return _write_payload(target, payload)
