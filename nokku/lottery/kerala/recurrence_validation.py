"""Kerala winning-pattern adapter for reusable finite-space recurrence validation.

This layer owns only Kerala-domain cohort construction: numeric length, draw-date
partitioning, decimal number-space derivation, and lineage receipt. The actual
recurrence mathematics lives in Banyan and remains domain-neutral.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from banyan.recurrence import FiniteSpaceRecurrenceValidation, validate_finite_space_recurrence

from .winning_patterns import WinningNumberPattern


ADAPTER_CONTRACT = "kerala.numeric_length_recurrence.v1"


@dataclass(frozen=True, slots=True)
class KeralaNumericLengthRecurrenceResult:
    """Lineage-preserving receipt for one numeric-length historical cohort."""

    status: str
    contract: str
    evidence_checkpoint: str
    digit_length: int
    number_space_size: int
    discovery_end: date
    validation_start: date
    input_pattern_count: int
    cohort_pattern_count: int
    discovery_pattern_count: int
    validation_pattern_count: int
    unassigned_pattern_count: int
    transformations: tuple[str, ...]
    analysis: FiniteSpaceRecurrenceValidation
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def validate_numeric_length_recurrence(
    patterns: Iterable[WinningNumberPattern],
    *,
    digit_length: int,
    discovery_end: date,
    validation_start: date,
    evidence_checkpoint: str,
) -> KeralaNumericLengthRecurrenceResult:
    """Validate recurrence for one caller-selected numeric length and date split."""
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

    discovery_values = tuple(
        pattern.numeric_part for pattern in cohort if pattern.draw_date <= discovery_end
    )
    validation_values = tuple(
        pattern.numeric_part for pattern in cohort if pattern.draw_date >= validation_start
    )
    unassigned_count = len(cohort) - len(discovery_values) - len(validation_values)

    number_space_size = 10**digit_length
    analysis = validate_finite_space_recurrence(
        discovery_values,
        validation_values,
        space_size=number_space_size,
    )

    transformations = (
        f"filtered winning patterns to numeric length {digit_length}",
        f"discovery cohort includes draw dates through {discovery_end.isoformat()}",
        f"validation cohort includes draw dates from {validation_start.isoformat()}",
        f"decimal finite-space size derived as 10**{digit_length}={number_space_size}",
    )

    return KeralaNumericLengthRecurrenceResult(
        status=analysis.status,
        contract=ADAPTER_CONTRACT,
        evidence_checkpoint=evidence_checkpoint.strip(),
        digit_length=digit_length,
        number_space_size=number_space_size,
        discovery_end=discovery_end,
        validation_start=validation_start,
        input_pattern_count=len(normalized),
        cohort_pattern_count=len(cohort),
        discovery_pattern_count=len(discovery_values),
        validation_pattern_count=len(validation_values),
        unassigned_pattern_count=unassigned_count,
        transformations=transformations,
        analysis=analysis,
        failures=analysis.failures,
        uncertainty=analysis.uncertainty,
    )
