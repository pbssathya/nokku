"""Derived numeric-pattern view over normalized Kerala lottery winning entries.

The winning corpus remains the ticket/prize-level factual view. This module
builds a second, deterministic structural view in which one numeric part is
counted once per draw while retaining all ticket, series, prize-tier, and prize
amount provenance that produced that pattern.

It performs no numerology, recurrence scoring, astrology, or BUY/SKIP policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .winning_corpus import WinningNumberEntry


_CONSOLATION_LABELS = frozenset({"cons prize", "consolation prize"})


def canonical_prize_tier(label: str) -> str:
    """Return the canonical analytical label while preserving raw labels elsewhere."""
    normalized = " ".join(str(label or "").split())
    if normalized.casefold() in _CONSOLATION_LABELS:
        return "Consolation Prize"
    return normalized


@dataclass(frozen=True, slots=True)
class WinningNumberPattern:
    """One unique numeric pattern within one draw, with complete provenance."""

    source: str
    draw_serial: int | None
    draw_date: date
    lottery_name: str
    lottery_code: str | None
    numeric_part: str
    ticket_occurrence_count: int
    raw_prize_tiers: tuple[str, ...]
    canonical_prize_tiers: tuple[str, ...]
    prize_amounts: tuple[int, ...]
    series: tuple[str, ...]
    includes_first_prize: bool
    includes_consolation: bool


@dataclass(frozen=True, slots=True)
class WinningPatternViewResult:
    """Receipt for deriving the unique numeric-pattern population."""

    status: str
    patterns: tuple[WinningNumberPattern, ...]
    ticket_entry_count: int
    unique_pattern_count: int
    collapsed_occurrence_count: int
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _append_unique(values: list[object], value: object) -> None:
    if value not in values:
        values.append(value)


def build_numeric_pattern_view(
    entries: Iterable[WinningNumberEntry],
) -> WinningPatternViewResult:
    """Collapse repeated ticket occurrences to one number per draw.

    Grouping is by ``(source, numeric_part)``. This intentionally collapses a
    first-prize number and its same-number consolation tickets into one
    structural observation, while retaining the prize and series provenance so
    consumers that need ticket-level or prize-level semantics can still inspect
    what produced the pattern.
    """
    uncertainty: list[str] = []
    ordered_keys: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], dict[str, object]] = {}
    ticket_count = 0

    for entry in entries:
        ticket_count += 1
        key = (entry.source, entry.numeric_part)
        existing = groups.get(key)
        if existing is None:
            existing = {
                "source": entry.source,
                "draw_serial": entry.draw_serial,
                "draw_date": entry.draw_date,
                "lottery_name": entry.lottery_name,
                "lottery_code": entry.lottery_code,
                "numeric_part": entry.numeric_part,
                "ticket_occurrence_count": 0,
                "raw_prize_tiers": [],
                "canonical_prize_tiers": [],
                "prize_amounts": [],
                "series": [],
            }
            groups[key] = existing
            ordered_keys.append(key)
        else:
            if (
                existing["draw_date"] != entry.draw_date
                or existing["lottery_name"] != entry.lottery_name
                or existing["lottery_code"] != entry.lottery_code
            ):
                uncertainty.append(
                    "numeric pattern group has inconsistent draw metadata: "
                    f"source={entry.source}, number={entry.numeric_part}"
                )

        existing["ticket_occurrence_count"] = int(existing["ticket_occurrence_count"]) + 1
        raw_tiers = existing["raw_prize_tiers"]
        canonical_tiers = existing["canonical_prize_tiers"]
        amounts = existing["prize_amounts"]
        series_values = existing["series"]
        assert isinstance(raw_tiers, list)
        assert isinstance(canonical_tiers, list)
        assert isinstance(amounts, list)
        assert isinstance(series_values, list)

        _append_unique(raw_tiers, entry.prize_tier)
        _append_unique(canonical_tiers, canonical_prize_tier(entry.prize_tier))
        if entry.prize_amount is not None:
            _append_unique(amounts, entry.prize_amount)
        if entry.series is not None:
            _append_unique(series_values, entry.series)

    patterns: list[WinningNumberPattern] = []
    for key in ordered_keys:
        group = groups[key]
        raw_tiers = tuple(str(value) for value in group["raw_prize_tiers"])
        canonical_tiers = tuple(str(value) for value in group["canonical_prize_tiers"])
        prize_amounts = tuple(int(value) for value in group["prize_amounts"])
        series_values = tuple(str(value) for value in group["series"])
        patterns.append(
            WinningNumberPattern(
                source=str(group["source"]),
                draw_serial=group["draw_serial"],
                draw_date=group["draw_date"],
                lottery_name=str(group["lottery_name"]),
                lottery_code=group["lottery_code"],
                numeric_part=str(group["numeric_part"]),
                ticket_occurrence_count=int(group["ticket_occurrence_count"]),
                raw_prize_tiers=raw_tiers,
                canonical_prize_tiers=canonical_tiers,
                prize_amounts=prize_amounts,
                series=series_values,
                includes_first_prize="1st Prize" in canonical_tiers,
                includes_consolation="Consolation Prize" in canonical_tiers,
            )
        )

    status = "partial" if uncertainty else "success"
    unique_count = len(patterns)
    return WinningPatternViewResult(
        status=status,
        patterns=tuple(patterns),
        ticket_entry_count=ticket_count,
        unique_pattern_count=unique_count,
        collapsed_occurrence_count=ticket_count - unique_count,
        uncertainty=tuple(uncertainty),
    )
