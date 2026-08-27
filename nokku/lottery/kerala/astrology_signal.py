"""Living-layer adapter for the experimental Lakshmi astrology observation.

This module only turns explicit user-owned birth inputs into an astrology
snapshot. It does not rank candidate dates or influence BUY/SKIP policy.
"""

from __future__ import annotations

from datetime import datetime

from nokku.preferences import UserPreferences

from .astrology import (
    VimshottariSnapshot,
    experimental_natal_moon_supports_birth_at,
    lakshmi_astrology_snapshot,
)


def lakshmi_astrology_observation(
    *,
    user_preferences: UserPreferences,
    target_at: datetime,
) -> VimshottariSnapshot | None:
    """Return an experimental astrology observation when birth time is supported.

    Birth date/time/location remain user-owned inputs. Astrology is skipped when
    the birth profile or its own timezone is missing, and it also abstains when
    Nokku has not yet derived a natal Moon longitude for that birth instant. The
    user's current timezone is deliberately never substituted for birth timezone.
    """
    if target_at.tzinfo is None:
        raise ValueError("Lakshmi astrology target instant must be timezone-aware.")

    if user_preferences.birth is None:
        return None

    birth_at = user_preferences.birth.as_aware_datetime()
    if birth_at is None:
        return None

    if not experimental_natal_moon_supports_birth_at(birth_at):
        return None

    return lakshmi_astrology_snapshot(birth_at, target_at)
