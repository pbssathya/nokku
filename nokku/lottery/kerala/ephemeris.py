"""Minimal astronomical position capability for Project Lakshmi.

This module deliberately stops at astronomical facts. It does not rank dates,
interpret planets, or influence BUY/SKIP policy.

The tropical positions come from Skyfield + the packaged JPL DE421 kernel. The
sidereal conversion uses Nokku's declared Lahiri convention: a J2000 Lahiri
anchor of 23°51′25.53″ evolved with the IAU 2006 general-precession-in-
longitude polynomial. This realization was validated in the living habitat
against the recovered 12 Sep 2026 Lakshmi Moon observation before being added
here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import floor
from typing import Literal

from skyfield.api import Loader
from skyfield_data import get_skyfield_data_path


J2000_TT_JD = 2451545.0
LAHIRI_J2000_DEG = 23.0 + 51.0 / 60.0 + 25.53 / 3600.0
LAHIRI_REALIZATION = "lahiri_j2000_23d51m25.53s_iau2006_pA"
EPHEMERIS_KERNEL = "de421.bsp"

SIGN_NAMES = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)

SupportedBody = Literal["moon", "jupiter"]
_BODY_KEYS: dict[SupportedBody, str] = {
    "moon": "moon",
    "jupiter": "jupiter barycenter",
}


@dataclass(frozen=True, slots=True)
class SiderealPosition:
    """One explainable geocentric apparent ecliptic position receipt."""

    body: SupportedBody
    target_at: datetime
    tropical_longitude_deg: float
    sidereal_longitude_deg: float
    ayanamsa_deg: float
    sign_index: int
    sign_name: str
    degrees_in_sign: float
    ephemeris_kernel: str = EPHEMERIS_KERNEL
    ayanamsa_realization: str = LAHIRI_REALIZATION
    status: str = "experimental"


@dataclass(frozen=True, slots=True)
class LakshmiTransitReceipt:
    """Factual Moon/Jupiter positions at one explicit Lakshmi target instant."""

    target_at: datetime
    moon: SiderealPosition
    jupiter: SiderealPosition
    ephemeris_kernel: str = EPHEMERIS_KERNEL
    ayanamsa_realization: str = LAHIRI_REALIZATION
    status: str = "experimental"


def general_precession_iau2006_deg(tt_jd: float) -> float:
    """Return IAU 2006 general precession in longitude from J2000, in degrees.

    ``T`` is Julian centuries of TT from J2000.0. Coefficients are the IAU
    2006 / P03 ``p_A`` polynomial, expressed here in arcseconds before
    conversion to degrees.
    """
    t = (float(tt_jd) - J2000_TT_JD) / 36525.0
    arcsec = (
        5028.796195 * t
        + 1.1054348 * t**2
        + 0.00007964 * t**3
        - 0.000023857 * t**4
        - 0.0000000383 * t**5
    )
    return arcsec / 3600.0


def lahiri_ayanamsa_deg(tt_jd: float) -> float:
    """Return Nokku's explicit experimental Lahiri ayanamsa realization."""
    return (LAHIRI_J2000_DEG + general_precession_iau2006_deg(tt_jd)) % 360.0


def _loader() -> Loader:
    """Return an offline loader rooted in the packaged Skyfield data."""
    return Loader(get_skyfield_data_path(), expire=False)


def sidereal_position(body: SupportedBody, *, target_at: datetime) -> SiderealPosition:
    """Return one Moon/Jupiter sidereal position at an aware target instant.

    No network access is needed: DE421 is supplied by ``skyfield-data`` and the
    Skyfield built-in timescale is used.
    """
    if target_at.tzinfo is None or target_at.utcoffset() is None:
        raise ValueError("Ephemeris target instant must be timezone-aware.")
    if body not in _BODY_KEYS:
        raise ValueError(f"Unsupported Lakshmi ephemeris body: {body}")

    load = _loader()
    timescale = load.timescale(builtin=True)
    target = timescale.from_datetime(target_at)
    ephemeris = load(EPHEMERIS_KERNEL)
    try:
        earth = ephemeris["earth"]
        apparent = earth.at(target).observe(ephemeris[_BODY_KEYS[body]]).apparent()
        _, tropical_longitude, _ = apparent.ecliptic_latlon(epoch="date")
        ayanamsa = lahiri_ayanamsa_deg(target.tt)
        sidereal = (tropical_longitude.degrees - ayanamsa) % 360.0
        sign_index = floor(sidereal / 30.0)
        degrees_in_sign = sidereal - sign_index * 30.0
        return SiderealPosition(
            body=body,
            target_at=target_at,
            tropical_longitude_deg=tropical_longitude.degrees,
            sidereal_longitude_deg=sidereal,
            ayanamsa_deg=ayanamsa,
            sign_index=sign_index,
            sign_name=SIGN_NAMES[sign_index],
            degrees_in_sign=degrees_in_sign,
        )
    finally:
        ephemeris.close()


def lakshmi_transit_receipt(*, target_at: datetime) -> LakshmiTransitReceipt:
    """Return the minimal factual transit receipt currently used by Lakshmi.

    This deliberately contains no astrological judgment. It only preserves the
    two independently proven astronomical inputs needed by the current living
    experiment: Moon and Jupiter Lahiri-sidereal positions.
    """
    moon = sidereal_position("moon", target_at=target_at)
    jupiter = sidereal_position("jupiter", target_at=target_at)
    return LakshmiTransitReceipt(
        target_at=target_at,
        moon=moon,
        jupiter=jupiter,
    )
