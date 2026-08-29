"""Explicit experimental astrology convention for Lakshmi.

This module contains application methodology and generic Vimshottari arithmetic.
User-owned birth facts and derived natal Moon inputs must be supplied by callers;
no person's derived astrology data belongs in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class LakshmiAstrologyConvention:
    """Declared convention used by the experimental Lakshmi astrology slice."""

    ayanamsa: str
    dasha_system: str
    dasha_year_basis: str
    dasha_days_per_year: float
    status: str = "experimental"


LAKSHMI_ASTROLOGY_CONVENTION = LakshmiAstrologyConvention(
    ayanamsa="lahiri",
    dasha_system="vimshottari",
    dasha_year_basis="julian_365_25",
    dasha_days_per_year=365.25,
)

VIMSHOTTARI_SEQUENCE = (
    "Ketu",
    "Venus",
    "Sun",
    "Moon",
    "Mars",
    "Rahu",
    "Jupiter",
    "Saturn",
    "Mercury",
)

VIMSHOTTARI_YEARS = {
    "Ketu": 7,
    "Venus": 20,
    "Sun": 6,
    "Moon": 10,
    "Mars": 7,
    "Rahu": 18,
    "Jupiter": 16,
    "Saturn": 19,
    "Mercury": 17,
}

NAKSHATRAS = (
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
)


@dataclass(frozen=True, slots=True)
class VimshottariSnapshot:
    """Experimental Vimshottari periods active at one target instant."""

    natal_nakshatra: str
    natal_nakshatra_lord: str
    mahadasha: str
    antardasha: str
    mahadasha_start: datetime
    mahadasha_end: datetime
    antardasha_start: datetime
    antardasha_end: datetime
    status: str = "experimental"


def vimshottari_snapshot(
    natal_moon_longitude: float,
    birth_at: datetime,
    target_at: datetime,
    *,
    convention: LakshmiAstrologyConvention = LAKSHMI_ASTROLOGY_CONVENTION,
) -> VimshottariSnapshot:
    """Return the Vimshottari Mahadasha/Antardasha active at ``target_at``.

    ``natal_moon_longitude`` is a caller-supplied sidereal lunar longitude in
    degrees. This function applies the declared dasha convention; it does not
    choose or derive an ephemeris value for any user.
    """
    if birth_at.tzinfo is None or birth_at.utcoffset() is None:
        raise ValueError("Birth instant must be timezone-aware.")
    if target_at.tzinfo is None or target_at.utcoffset() is None:
        raise ValueError("Target instant must be timezone-aware.")
    if target_at < birth_at:
        raise ValueError("Target instant cannot precede birth instant.")

    moon = natal_moon_longitude % 360.0
    nakshatra_size = 360.0 / 27.0
    nakshatra_index = int(moon // nakshatra_size)
    within_nakshatra = moon - (nakshatra_index * nakshatra_size)
    natal_lord = VIMSHOTTARI_SEQUENCE[nakshatra_index % len(VIMSHOTTARI_SEQUENCE)]

    elapsed_fraction = within_nakshatra / nakshatra_size
    natal_md_elapsed_days = (
        elapsed_fraction
        * VIMSHOTTARI_YEARS[natal_lord]
        * convention.dasha_days_per_year
    )
    current_start = birth_at - timedelta(days=natal_md_elapsed_days)
    current_index = VIMSHOTTARI_SEQUENCE.index(natal_lord)

    for _ in range(100):
        current_lord = VIMSHOTTARI_SEQUENCE[current_index]
        current_end = current_start + timedelta(
            days=VIMSHOTTARI_YEARS[current_lord] * convention.dasha_days_per_year
        )
        if current_start <= target_at < current_end:
            mahadasha = current_lord
            mahadasha_start = current_start
            mahadasha_end = current_end
            break
        current_start = current_end
        current_index = (current_index + 1) % len(VIMSHOTTARI_SEQUENCE)
    else:  # pragma: no cover - defensive guard for absurdly distant targets
        raise ValueError("Target instant is outside the supported dasha horizon.")

    antardasha_start = mahadasha_start
    antardasha_index = VIMSHOTTARI_SEQUENCE.index(mahadasha)
    for _ in range(len(VIMSHOTTARI_SEQUENCE)):
        antardasha = VIMSHOTTARI_SEQUENCE[antardasha_index]
        antardasha_end = antardasha_start + timedelta(
            days=(
                VIMSHOTTARI_YEARS[mahadasha]
                * VIMSHOTTARI_YEARS[antardasha]
                / 120.0
                * convention.dasha_days_per_year
            )
        )
        if antardasha_start <= target_at < antardasha_end:
            break
        antardasha_start = antardasha_end
        antardasha_index = (antardasha_index + 1) % len(VIMSHOTTARI_SEQUENCE)
    else:  # pragma: no cover - the nine subperiods exactly span the Mahadasha
        raise RuntimeError("Could not resolve Antardasha within Mahadasha.")

    return VimshottariSnapshot(
        natal_nakshatra=NAKSHATRAS[nakshatra_index],
        natal_nakshatra_lord=natal_lord,
        mahadasha=mahadasha,
        antardasha=antardasha,
        mahadasha_start=mahadasha_start,
        mahadasha_end=mahadasha_end,
        antardasha_start=antardasha_start,
        antardasha_end=antardasha_end,
    )
