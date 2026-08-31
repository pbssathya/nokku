"""Domain-neutral recurrence validation over a caller-defined finite space.

The caller supplies observed labels and the size of the finite space they came
from. This module reports descriptive recurrence plus an explicit mechanical
uniform/independent baseline. It has no knowledge of lottery domains,
applications, prize tiers, users, or decision policy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import exp, log1p
from typing import Iterable


ANALYSIS_CONTRACT = "banyan.finite_space_recurrence.v1"
_BASELINE_ASSUMPTIONS = (
    "observations are compared with a finite-space control in which each draw is independent",
    "the finite-space control assigns equal probability to every value and samples with replacement",
    "the control is a mechanical reference, not an assertion that the real generating process satisfies those assumptions",
)


@dataclass(frozen=True, slots=True)
class FiniteSpaceCohortSummary:
    """Observed recurrence and mechanical expectations for one cohort."""

    sample_size: int
    space_size: int
    distinct_value_count: int
    recurring_value_count: int
    repeat_occurrence_count: int
    expected_distinct_value_count: float
    expected_recurring_value_count: float
    expected_repeat_occurrence_count: float
    recurring_value_ratio_to_expected: float | None
    repeat_occurrence_ratio_to_expected: float | None


@dataclass(frozen=True, slots=True)
class DiscoveryValidationPersistence:
    """Persistence of candidates frozen from discovery before validation is read."""

    discovery_sample_size: int
    validation_sample_size: int
    discovery_recurring_value_count: int
    frozen_candidate_count: int
    observed_surviving_candidate_count: int
    expected_surviving_candidate_count: float
    survival_ratio_to_expected: float | None
    surviving_values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FiniteSpaceRecurrenceValidation:
    """Truthful receipt for discovery/validation recurrence analysis."""

    status: str
    contract: str
    space_size: int
    assumptions: tuple[str, ...]
    discovery: FiniteSpaceCohortSummary
    validation: FiniteSpaceCohortSummary
    combined: FiniteSpaceCohortSummary
    persistence: DiscoveryValidationPersistence
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _probability_unseen(sample_size: int, space_size: int) -> float:
    if sample_size == 0:
        return 1.0
    if space_size == 1:
        return 0.0
    return exp(sample_size * log1p(-1.0 / space_size))


def _probability_seen_once(sample_size: int, space_size: int) -> float:
    if sample_size == 0:
        return 0.0
    if space_size == 1:
        return 1.0 if sample_size == 1 else 0.0
    return (
        sample_size
        / space_size
        * exp((sample_size - 1) * log1p(-1.0 / space_size))
    )


def _ratio(observed: int, expected: float) -> float | None:
    if expected <= 0.0:
        return None
    return observed / expected


def _summarize(values: tuple[str, ...], space_size: int) -> FiniteSpaceCohortSummary:
    counts = Counter(values)
    sample_size = len(values)
    distinct_count = len(counts)
    recurring_count = sum(1 for count in counts.values() if count > 1)
    repeat_occurrence_count = sample_size - distinct_count

    probability_unseen = _probability_unseen(sample_size, space_size)
    probability_seen_once = _probability_seen_once(sample_size, space_size)

    expected_distinct = max(0.0, space_size * (1.0 - probability_unseen))
    expected_recurring = max(
        0.0,
        space_size * (1.0 - probability_unseen - probability_seen_once),
    )
    expected_repeat_occurrences = max(0.0, sample_size - expected_distinct)

    return FiniteSpaceCohortSummary(
        sample_size=sample_size,
        space_size=space_size,
        distinct_value_count=distinct_count,
        recurring_value_count=recurring_count,
        repeat_occurrence_count=repeat_occurrence_count,
        expected_distinct_value_count=expected_distinct,
        expected_recurring_value_count=expected_recurring,
        expected_repeat_occurrence_count=expected_repeat_occurrences,
        recurring_value_ratio_to_expected=_ratio(recurring_count, expected_recurring),
        repeat_occurrence_ratio_to_expected=_ratio(
            repeat_occurrence_count,
            expected_repeat_occurrences,
        ),
    )


def validate_finite_space_recurrence(
    discovery_values: Iterable[str],
    validation_values: Iterable[str],
    *,
    space_size: int,
) -> FiniteSpaceRecurrenceValidation:
    """Compare recurrence with an explicit finite-space mechanical control.

    Discovery candidates are frozen solely from values that recur inside the
    discovery cohort. Validation values are consulted only after that candidate
    set has been fixed, preventing validation-to-discovery leakage.
    """
    if space_size < 1:
        raise ValueError("space_size must be at least 1")

    discovery = tuple(discovery_values)
    validation = tuple(validation_values)

    if any(not isinstance(value, str) or not value for value in discovery + validation):
        raise ValueError("recurrence values must be non-empty strings")

    discovery_counts = Counter(discovery)
    frozen_candidates = frozenset(
        value for value, count in discovery_counts.items() if count > 1
    )
    validation_values_seen = frozenset(validation)
    surviving_values = tuple(sorted(frozen_candidates & validation_values_seen))

    if space_size == 1:
        validation_hit_probability = 1.0 if validation else 0.0
    else:
        validation_hit_probability = 1.0 - _probability_unseen(
            len(validation),
            space_size,
        )

    expected_survivors = len(frozen_candidates) * validation_hit_probability
    uncertainty: list[str] = []

    combined = discovery + validation
    distinct_combined = len(set(combined))
    if distinct_combined > space_size:
        uncertainty.append(
            "observed distinct values exceed the caller-supplied finite space size"
        )

    persistence = DiscoveryValidationPersistence(
        discovery_sample_size=len(discovery),
        validation_sample_size=len(validation),
        discovery_recurring_value_count=len(frozen_candidates),
        frozen_candidate_count=len(frozen_candidates),
        observed_surviving_candidate_count=len(surviving_values),
        expected_surviving_candidate_count=expected_survivors,
        survival_ratio_to_expected=_ratio(len(surviving_values), expected_survivors),
        surviving_values=surviving_values,
    )

    return FiniteSpaceRecurrenceValidation(
        status="partial" if uncertainty else "success",
        contract=ANALYSIS_CONTRACT,
        space_size=space_size,
        assumptions=_BASELINE_ASSUMPTIONS,
        discovery=_summarize(discovery, space_size),
        validation=_summarize(validation, space_size),
        combined=_summarize(combined, space_size),
        persistence=persistence,
        uncertainty=tuple(uncertainty),
    )
