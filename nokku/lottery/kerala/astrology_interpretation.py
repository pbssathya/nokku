"""Minimal, explicit interpretation of Project Lakshmi transit evidence.

This layer is intentionally narrow. It converts independently derived natal
Moon/Jupiter/Ketu facts plus factual candidate transit receipts into the two
close-conjunction signals recovered from the living habitat:

- transit Moon close to natal Jupiter → supportive
- transit Moon close to natal Ketu → caution

It does not implement a generic Jyotish score and it does not influence
BUY/SKIP policy. The 1-degree conjunction orbs are explicit experimental
conventions introduced here; they are not claimed to be recovered historical
thresholds. If both signals ever occur together, the caution reading takes
precedence while both underlying signals remain visible in the receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nokku.preferences import UserPreferences

from .ephemeris import (
    LakshmiTransitReceipt,
    LunarNodeReceipt,
    SiderealPosition,
    lunar_node_receipt,
    sidereal_position,
)


MOON_NATAL_JUPITER_CONJUNCTION_ORB_DEG = 1.0
MOON_NATAL_KETU_CONJUNCTION_ORB_DEG = 1.0
INTERPRETATION_METHOD = "lakshmi_moon_natal_jupiter_ketu_v2"


@dataclass(frozen=True, slots=True)
class NatalAstrologyContextResult:
    """Truthful independently derived natal context needed by this slice."""

    status: str
    birth_at: datetime | None
    moon: SiderealPosition | None
    jupiter: SiderealPosition | None
    lunar_nodes: LunarNodeReceipt | None
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
    transit_moon_to_natal_ketu_separation_deg: float | None
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
    """Derive natal Moon/Jupiter/Ketu from stable user-owned birth facts.

    These geocentric and lunar-orbit facts need the birth instant but not house
    or ascendant geometry, so this slice does not geocode the birth location.
    """
    if user_preferences.birth is None:
        return NatalAstrologyContextResult(
            status="abstained",
            birth_at=None,
            moon=None,
            jupiter=None,
            lunar_nodes=None,
            failures=("birth_profile_missing",),
        )

    birth_at = user_preferences.birth.as_aware_datetime()
    if birth_at is None:
        return NatalAstrologyContextResult(
            status="abstained",
            birth_at=None,
            moon=None,
            jupiter=None,
            lunar_nodes=None,
            failures=("birth_timezone_missing",),
        )

    try:
        moon = sidereal_position("moon", target_at=birth_at)
        jupiter = sidereal_position("jupiter", target_at=birth_at)
        lunar_nodes = lunar_node_receipt(target_at=birth_at)
    except Exception as exc:  # keep optional symbolic evidence isolated
        return NatalAstrologyContextResult(
            status="unavailable",
            birth_at=birth_at,
            moon=None,
            jupiter=None,
            lunar_nodes=None,
            failures=(f"{type(exc).__name__}: {exc}",),
        )

    return NatalAstrologyContextResult(
        status="success",
        birth_at=birth_at,
        moon=moon,
        jupiter=jupiter,
        lunar_nodes=lunar_nodes,
    )


def interpret_candidate_transit(
    *,
    transit: LakshmiTransitReceipt,
    natal_context: NatalAstrologyContextResult,
) -> CandidateAstrologyInterpretation:
    """Interpret only the recovered Moon↔Jupiter and Moon↔Ketu activations."""
    if (
        natal_context.status != "success"
        or natal_context.moon is None
        or natal_context.jupiter is None
        or natal_context.lunar_nodes is None
    ):
        return CandidateAstrologyInterpretation(
            target_at=transit.target_at,
            status="abstained",
            reading="unresolved",
            transit_moon_to_natal_jupiter_separation_deg=None,
            transit_moon_to_natal_moon_separation_deg=None,
            transit_moon_to_natal_ketu_separation_deg=None,
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
    moon_to_ketu = angular_separation_deg(
        transit.moon.sidereal_longitude_deg,
        natal_context.lunar_nodes.ketu_sidereal_longitude_deg,
    )

    signals: list[str] = []
    if moon_to_jupiter <= MOON_NATAL_JUPITER_CONJUNCTION_ORB_DEG:
        signals.append("transit_moon_close_to_natal_jupiter")
    if moon_to_ketu <= MOON_NATAL_KETU_CONJUNCTION_ORB_DEG:
        signals.append("transit_moon_close_to_natal_ketu")

    if "transit_moon_close_to_natal_ketu" in signals:
        reading = "caution"
    elif "transit_moon_close_to_natal_jupiter" in signals:
        reading = "supportive"
    else:
        reading = "unresolved"

    return CandidateAstrologyInterpretation(
        target_at=transit.target_at,
        status="success",
        reading=reading,
        transit_moon_to_natal_jupiter_separation_deg=moon_to_jupiter,
        transit_moon_to_natal_moon_separation_deg=moon_to_moon,
        transit_moon_to_natal_ketu_separation_deg=moon_to_ketu,
        signals=tuple(signals),
    )
