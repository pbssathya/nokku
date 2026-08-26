"""Explicit experimental astrology convention for Lakshmi.

This module records the analytical convention chosen for the current living
experiment. It is application methodology, not user-owned preference data and
must not be presented as recovered historical Project Lakshmi behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass


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
