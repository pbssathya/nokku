"""Living-layer adapter for the experimental Lakshmi astrology observation.

This module combines user-owned birth facts with an explicitly supplied derived
natal Moon input. It does not derive ephemeris data, rank candidate dates, or
influence BUY/SKIP policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math

from nokku.preferences import UserPreferences

from .astrology import VimshottariSnapshot, vimshottari_snapshot


@dataclass(frozen=True, slots=True)
class AstrologyObservationResult:
    """Truthful receipt for one experimental astrology observation attempt."""

    status: str
    observation: VimshottariSnapshot | None
    natal_moon_longitude: float | None
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def lakshmi_astrology_observation_result(
    *,
    user_preferences: UserPreferences,
    target_at: datetime,
    natal_moon_longitude: float | None = None,
) -> AstrologyObservationResult:
    """Return an astrology receipt from explicit user and derived inputs.

    Birth date/time/location remain user-owned inputs. ``natal_moon_longitude``
    is derived capability input supplied by the caller; this layer never borrows
    or hardcodes a person's Moon value. When required inputs are unavailable it
    abstains and reports why.
    """
    if target_at.tzinfo is None or target_at.utcoffset() is None:
        raise ValueError("Lakshmi astrology target instant must be timezone-aware.")

    if user_preferences.birth is None:
        return AstrologyObservationResult(
            status="abstained",
            observation=None,
            natal_moon_longitude=natal_moon_longitude,
            failures=("birth_profile_missing",),
        )

    birth_at = user_preferences.birth.as_aware_datetime()
    if birth_at is None:
        return AstrologyObservationResult(
            status="abstained",
            observation=None,
            natal_moon_longitude=natal_moon_longitude,
            failures=("birth_timezone_missing",),
        )

    if natal_moon_longitude is None:
        return AstrologyObservationResult(
            status="abstained",
            observation=None,
            natal_moon_longitude=None,
            uncertainty=("natal_moon_longitude_not_supplied",),
        )

    moon = float(natal_moon_longitude)
    if not math.isfinite(moon):
        raise ValueError("Natal Moon longitude must be a finite number.")

    observation = vimshottari_snapshot(
        moon,
        birth_at,
        target_at,
    )
    return AstrologyObservationResult(
        status="success",
        observation=observation,
        natal_moon_longitude=moon,
    )


def lakshmi_astrology_observation(
    *,
    user_preferences: UserPreferences,
    target_at: datetime,
    natal_moon_longitude: float | None = None,
) -> VimshottariSnapshot | None:
    """Compatibility view returning only the observation from the full receipt."""
    return lakshmi_astrology_observation_result(
        user_preferences=user_preferences,
        target_at=target_at,
        natal_moon_longitude=natal_moon_longitude,
    ).observation
