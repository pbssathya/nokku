"""Minimal, explicit interpretation of Project Lakshmi transit evidence.

This layer is intentionally narrow.  It converts independently derived natal
Moon/Jupiter positions plus factual candidate transit receipts into one
experimental signal recovered from the living habitat: a close transit-Moon to
natal-Jupiter conjunction.

It does not implement a generic Jyotish score and it does not influence
BUY/SKIP policy.  The 1-degree conjunction orb is an explicit experimental
convention introduced here; it is not claimed to be a recovered historical
threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nokku.preferences import UserPreferences

from .ephemeris import LakshmiTransitReceipt, SiderealPosition, sidereal_position


MOON_NATAL_JUPITER_CONJUNCTION_ORB_DEG = 1.0
INTERPRETATION_METHOD = "lakshmi_moon_natal_jupiter_conjunction_v1"


@dataclass(frozen=True, slots=True)
class NatalAstrologyContextResult:
    """Truthful independently derived natal context needed by this slice."""

    status: str
    birth_at: datetime | None
    moon: SiderealPosition | None
    jupiter: SiderealPosition | None
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateAstrologyInterpretation:
    """One explainable experimental interpretation of a factual transit receipt."""

    target_at: datetime
    status: str
    reading: str
    transit_moon_to_natal_jupiter_separation_deg: float | None
    transit_moon_to_natal_moon_separation_deg: float | None
    signals: tuple[str, ...] = ()
    method: str = INTERPRETATION_METHOD
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def angular_separation_deg(first: float, second: float) -> float:
    """Return the smallest angular separation between two zodiac longitudes."""
    delta = abs((float(first) - float(second)) % 360.0)
    return min(delta, 360.0 - delta)


def natal_astrology_context(
    *, user_preferences: UserPreferences
) -> NatalAstrologyContextResult:
    """Derive natal Moon/Jupiter from stable user-owned birth facts.

    The geocentric planetary positions need the birth instant but not house or
    ascendant geometry, so this slice does not geocode the birth location.
    """
    if user_preferences.birth is None:
        return NatalAstrologyContextResult(
            status="abstained",
            birth_at=None,
            moon=None,
            jupiter=None,
            failures=("birth_profile_missing",),
        )

    birth_at = user_preferences.birth.as_aware_datetime()
    if birth_at is None:
        return NatalAstrologyContextResult(
            status="abstained",
            birth_at=None,
            moon=None,
            jupiter=None,
            failures=("birth_timezone_missing",),
        )

    try:
        moon = sidereal_position("moon", target_at=birth_at)
        jupiter = sidereal_position("jupiter", target_at=birth_at)
    except Exception as exc:  # keep optional symbolic evidence isolated
        return NatalAstrologyContextResult(
            status="unavailable",
            birth_at=birth_at,
            moon=None,
            jupiter=None,
            failures=(f"{type(exc).__name__}: {exc}",),
        )

    return NatalAstrologyContextResult(
        status="success",
        birth_at=birth_at,
        moon=moon,
        jupiter=jupiter,
    )


def interpret_candidate_transit(
    *,
    transit: LakshmiTransitReceipt,
    natal_context: NatalAstrologyContextResult,
) -> CandidateAstrologyInterpretation:
    """Interpret only the recovered Moon↔natal-Jupiter activation signal."""
    if (
        natal_context.status != "success"
        or natal_context.moon is None
        or natal_context.jupiter is None
    ):
        return CandidateAstrologyInterpretation(
            target_at=transit.target_at,
            status="abstained",
            reading="unresolved",
            transit_moon_to_natal_jupiter_separation_deg=None,
            transit_moon_to_natal_moon_separation_deg=None,
            failures=natal_context.failures,
            uncertainty=natal_context.uncertainty,
        )

    moon_to_jupiter = angular_separation_deg(
        transit.moon.sidereal_longitude_deg,
        natal_context.jupiter.sidereal_longitude_deg,
    )
    moon_to_moon = angular_separation_deg(
        transit.moon.sidereal_longitude_deg,
        natal_context.moon.sidereal_longitude_deg,
    )

    signals: tuple[str, ...] = ()
    reading = "unresolved"
    if moon_to_jupiter <= MOON_NATAL_JUPITER_CONJUNCTION_ORB_DEG:
        signals = ("transit_moon_close_to_natal_jupiter",)
        reading = "supportive"

    return CandidateAstrologyInterpretation(
        target_at=transit.target_at,
        status="success",
        reading=reading,
        transit_moon_to_natal_jupiter_separation_deg=moon_to_jupiter,
        transit_moon_to_natal_moon_separation_deg=moon_to_moon,
        signals=signals,
    )
