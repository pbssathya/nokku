"""Application-neutral user-owned settings for the Banyan tree.

These are stable facts/preferences owned by the user and reusable by any Banyan
application or capability. Derived numerology, astrology, and application
experience do not belong here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
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
