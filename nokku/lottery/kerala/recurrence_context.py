"""Context-stratified Kerala recurrence validation over winning patterns.

This module owns only Kerala-domain cohort construction for caller-selected
context kinds. It reuses Banyan's finite-space recurrence validator unchanged
and performs no scoring, ranking, prediction, astrology, numerology, or
BUY/SKIP policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Literal

from banyan.recurrence import (
    FiniteSpaceRecurrenceValidation,
    validate_finite_space_recurrence,
)

from .winning_patterns import WinningNumberPattern


CONTEXT_CONTRACT = "kerala.context_recurrence.v1"
ContextKind = Literal["prize_tier", "lottery_code"]
_SUPPORTED_CONTEXT_KINDS = frozenset({"prize_tier", "lottery_code"})


@dataclass(frozen=True, slots=True)
class KeralaContextRecurrenceGroup:
    """One independently validated Kerala context cohort."""

    context_value: str
    discovery_pattern_count: int
    validation_pattern_count: int
    analysis: FiniteSpaceRecurrenceValidation


@dataclass(frozen=True, slots=True)
class KeralaContextRecurrenceResult:
    """Lineage-preserving receipt for one context-stratified analysis."""

    status: str
    contract: str
    evidence_checkpoint: str
    context_kind: str
    digit_length: int
    number_space_size: int
    discovery_end: date
    validation_start: date
    input_pattern_count: int
    cohort_pattern_count: int
    unassigned_pattern_count: int
    groups: tuple[KeralaContextRecurrenceGroup, ...]
    transformations: tuple[str, ...]
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _context_values(
    pattern: WinningNumberPattern,
    context_kind: ContextKind,
) -> tuple[str, ...]:
    if context_kind == "lottery_code":
        if pattern.lottery_code is None or not pattern.lottery_code.strip():
            return ()
        return (pattern.lottery_code.strip(),)

    return tuple(
        value.strip()
        for value in pattern.canonical_prize_tiers
        if value.strip()
    )


def validate_context_recurrence(
    patterns: Iterable[WinningNumberPattern],
    *,
    context_kind: ContextKind,
    digit_length: int,
    discovery_end: date,
    validation_start: date,
    evidence_checkpoint: str,
) -> KeralaContextRecurrenceResult:
    """Validate recurrence independently inside caller-selected Kerala contexts."""
    if context_kind not in _SUPPORTED_CONTEXT_KINDS:
        raise ValueError(
            "context_kind must be one of: lottery_code, prize_tier"
        )
    if digit_length < 1:
        raise ValueError("digit_length must be at least 1")
    if validation_start <= discovery_end:
        raise ValueError("validation_start must be after discovery_end")
    if not evidence_checkpoint.strip():
        raise ValueError("evidence_checkpoint must not be empty")

    normalized = tuple(patterns)
    cohort = tuple(
        pattern for pattern in normalized if len(pattern.numeric_part) == digit_length
    )
    number_space_size = 10**digit_length

    discovery_values: dict[str, list[str]] = {}
    validation_values: dict[str, list[str]] = {}
    uncertainty: list[str] = []
    unassigned_pattern_count = 0

    for pattern in cohort:
        if pattern.draw_date <= discovery_end:
            target = discovery_values
        elif pattern.draw_date >= validation_start:
            target = validation_values
        else:
            unassigned_pattern_count += 1
            continue

        context_values = _context_values(pattern, context_kind)
        if not context_values:
            uncertainty.append(
                "winning pattern has no usable context value: "
                f"context_kind={context_kind}, source={pattern.source}, "
                f"number={pattern.numeric_part}"
            )
            continue

        for context_value in context_values:
            target.setdefault(context_value, []).append(pattern.numeric_part)

    context_names = sorted(set(discovery_values) | set(validation_values))
    groups: list[KeralaContextRecurrenceGroup] = []
    failures: list[str] = []

    for context_value in context_names:
        discovery = tuple(discovery_values.get(context_value, ()))
        validation = tuple(validation_values.get(context_value, ()))
        analysis = validate_finite_space_recurrence(
            discovery,
            validation,
            space_size=number_space_size,
        )
        failures.extend(
            f"context={context_value}: {item}" for item in analysis.failures
        )
        uncertainty.extend(
            f"context={context_value}: {item}" for item in analysis.uncertainty
        )
        groups.append(
            KeralaContextRecurrenceGroup(
                context_value=context_value,
                discovery_pattern_count=len(discovery),
                validation_pattern_count=len(validation),
                analysis=analysis,
            )
        )

    transformations = (
        f"filtered winning patterns to numeric length {digit_length}",
        f"stratified cohort by caller-selected context kind {context_kind}",
        f"discovery cohort includes draw dates through {discovery_end.isoformat()}",
        f"validation cohort includes draw dates from {validation_start.isoformat()}",
        f"decimal finite-space size derived as 10**{digit_length}={number_space_size}",
        "multi-valued prize-tier provenance contributes the same pattern to each applicable prize-tier context without duplicating it inside one context",
    )

    status = "partial" if failures or uncertainty else "success"
    return KeralaContextRecurrenceResult(
        status=status,
        contract=CONTEXT_CONTRACT,
        evidence_checkpoint=evidence_checkpoint.strip(),
        context_kind=context_kind,
        digit_length=digit_length,
        number_space_size=number_space_size,
        discovery_end=discovery_end,
        validation_start=validation_start,
        input_pattern_count=len(normalized),
        cohort_pattern_count=len(cohort),
        unassigned_pattern_count=unassigned_pattern_count,
        groups=tuple(groups),
        transformations=transformations,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )
