"""Anonymous numerology over a historical-number evidence receipt.

This module composes the already-derived structural facts from
:mod:`banyan.historical_numbers` with explicit, caller-supplied numerology
references. It intentionally does not reread raw historical observations and
knows nothing about lotteries, users, dates of birth, astrology, scoring, or
decision policy.

Recurrence expectations remain the responsibility of :mod:`banyan.recurrence`.
This layer reports only numerological relationships that are derivable from the
upstream historical-number receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .historical_numbers import (
    ANALYSIS_CONTRACT as HISTORICAL_NUMBERS_CONTRACT,
    HistoricalNumberAnalysis,
)
from .numerology import NumerologyReference


ANALYSIS_CONTRACT = "banyan.anonymous_historical_numerology.v1"
_SUPPORTED_METRICS = (
    "digital_root_match",
    "reference_digit_repeated",
    "last_digit_match",
)


@dataclass(frozen=True, slots=True)
class AnonymousNumerologyBaseline:
    """Explicit expected rate for one metric/reference/number-length cohort."""

    digit_length: int
    metric: str
    reference_label: str
    expected_rate: float


@dataclass(frozen=True, slots=True)
class AnonymousNumerologyMetric:
    """Observed anonymous numerology relationship plus optional baseline."""

    metric: str
    reference_label: str
    reference_value: int
    observed_count: int
    sample_size: int
    observed_rate: float
    baseline_rate: float | None
    delta_from_baseline: float | None


@dataclass(frozen=True, slots=True)
class AnonymousNumerologyLengthSummary:
    """Anonymous numerology observations for one numeric-length population."""

    digit_length: int
    sample_size: int
    metrics: tuple[AnonymousNumerologyMetric, ...]


@dataclass(frozen=True, slots=True)
class AnonymousHistoricalNumerologyAnalysis:
    """Lineage-preserving anonymous numerology receipt."""

    status: str
    contract: str
    upstream_contract: str
    evidence_checkpoint: str
    requested_start: date | None
    requested_end: date | None
    effective_start: date | None
    effective_end: date | None
    references: tuple[NumerologyReference, ...]
    input_record_count: int
    selected_record_count: int
    analyzed_record_count: int
    length_summaries: tuple[AnonymousNumerologyLengthSummary, ...]
    transformations: tuple[str, ...]
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _validate_references(
    references: Iterable[NumerologyReference],
) -> tuple[NumerologyReference, ...]:
    normalized = tuple(references)
    if not normalized:
        raise ValueError("at least one anonymous numerology reference is required")

    seen_labels: set[str] = set()
    for reference in normalized:
        label = reference.label.strip()
        if not label:
            raise ValueError("numerology reference labels must not be empty")
        if reference.value < 0 or reference.value > 9:
            raise ValueError("numerology reference values must be reduced digits from 0 to 9")
        if label in seen_labels:
            raise ValueError(f"duplicate numerology reference label: {label}")
        seen_labels.add(label)

    return normalized


def _validate_baselines(
    baselines: Iterable[AnonymousNumerologyBaseline],
    *,
    reference_labels: set[str],
) -> dict[tuple[int, str, str], float]:
    lookup: dict[tuple[int, str, str], float] = {}
    for baseline in baselines:
        if baseline.digit_length < 1:
            raise ValueError("baseline digit_length must be at least 1")
        if baseline.metric not in _SUPPORTED_METRICS:
            raise ValueError(f"unsupported anonymous numerology metric: {baseline.metric}")
        label = baseline.reference_label.strip()
        if not label:
            raise ValueError("baseline reference labels must not be empty")
        if label not in reference_labels:
            raise ValueError(f"baseline references unknown label: {label}")
        if baseline.expected_rate < 0 or baseline.expected_rate > 1:
            raise ValueError("baseline expected_rate must be between 0 and 1")
        key = (baseline.digit_length, baseline.metric, label)
        if key in lookup:
            raise ValueError(f"duplicate anonymous numerology baseline: {key!r}")
        lookup[key] = baseline.expected_rate
    return lookup


def _metric(
    *,
    metric: str,
    reference: NumerologyReference,
    observed_count: int,
    sample_size: int,
    baseline_lookup: dict[tuple[int, str, str], float],
    digit_length: int,
) -> AnonymousNumerologyMetric:
    observed_rate = observed_count / sample_size if sample_size else 0.0
    baseline_rate = baseline_lookup.get(
        (digit_length, metric, reference.label.strip())
    )
    return AnonymousNumerologyMetric(
        metric=metric,
        reference_label=reference.label.strip(),
        reference_value=reference.value,
        observed_count=observed_count,
        sample_size=sample_size,
        observed_rate=observed_rate,
        baseline_rate=baseline_rate,
        delta_from_baseline=(
            observed_rate - baseline_rate
            if baseline_rate is not None
            else None
        ),
    )


def analyze_anonymous_historical_numerology(
    history: HistoricalNumberAnalysis,
    *,
    references: Iterable[NumerologyReference],
    baselines: Iterable[AnonymousNumerologyBaseline] = (),
) -> AnonymousHistoricalNumerologyAnalysis:
    """Interpret an existing historical-number receipt without rereading raw data.

    Supported v1 relationships are those already preserved by
    ``banyan.historical_numbers.v1``:

    * digital-root equality with an explicit reference digit;
    * presence of that digit at least twice in a historical number; and
    * last-digit equality when the upstream snapshot contains width-1 endings.

    The upstream v1 receipt does not preserve arbitrary digit-presence counts, so
    this module deliberately does not fabricate a ``reference_digit_present``
    metric. Baselines are optional and always caller-supplied.
    """
    if history.contract != HISTORICAL_NUMBERS_CONTRACT:
        raise ValueError(
            "history must use the banyan.historical_numbers.v1 contract"
        )

    normalized_references = _validate_references(references)
    baseline_lookup = _validate_baselines(
        baselines,
        reference_labels={item.label.strip() for item in normalized_references},
    )

    uncertainty = list(history.uncertainty)
    failures = list(history.failures)
    summaries: list[AnonymousNumerologyLengthSummary] = []

    for length_summary in history.length_summaries:
        sample_size = length_summary.sample_size
        root_counts = dict(length_summary.digital_root_counts)
        repeated_counts = dict(length_summary.repeated_digit_counts)
        last_digit_counts = {
            item.ending: item.observed_count
            for item in length_summary.ending_counts
            if item.width == 1
        }
        has_last_digit_evidence = bool(last_digit_counts) or sample_size == 0

        metrics: list[AnonymousNumerologyMetric] = []
        for reference in normalized_references:
            metrics.append(
                _metric(
                    metric="digital_root_match",
                    reference=reference,
                    observed_count=root_counts.get(reference.value, 0),
                    sample_size=sample_size,
                    baseline_lookup=baseline_lookup,
                    digit_length=length_summary.digit_length,
                )
            )
            metrics.append(
                _metric(
                    metric="reference_digit_repeated",
                    reference=reference,
                    observed_count=repeated_counts.get(reference.value, 0),
                    sample_size=sample_size,
                    baseline_lookup=baseline_lookup,
                    digit_length=length_summary.digit_length,
                )
            )
            if has_last_digit_evidence:
                metrics.append(
                    _metric(
                        metric="last_digit_match",
                        reference=reference,
                        observed_count=last_digit_counts.get(str(reference.value), 0),
                        sample_size=sample_size,
                        baseline_lookup=baseline_lookup,
                        digit_length=length_summary.digit_length,
                    )
                )

        if sample_size and not has_last_digit_evidence:
            uncertainty.append(
                "last_digit_match unavailable because upstream historical-number "
                f"receipt omitted ending width 1 for digit_length={length_summary.digit_length}"
            )

        summaries.append(
            AnonymousNumerologyLengthSummary(
                digit_length=length_summary.digit_length,
                sample_size=sample_size,
                metrics=tuple(metrics),
            )
        )

    transformations = (
        "consumed banyan.historical_numbers.v1 without rereading raw historical observations",
        "kept numeric-length populations separate exactly as supplied by the upstream receipt",
        "compared only explicit caller-supplied reduced numerology references",
        "derived digital-root, repeated-reference-digit, and available last-digit relationships from upstream aggregates",
        "applied only explicit caller-supplied baselines; no generating-process baseline was invented",
        "did not derive arbitrary digit-presence metrics because the upstream v1 receipt does not preserve that fact",
    )

    status = "partial" if history.status != "success" or failures or uncertainty else "success"
    return AnonymousHistoricalNumerologyAnalysis(
        status=status,
        contract=ANALYSIS_CONTRACT,
        upstream_contract=history.contract,
        evidence_checkpoint=history.evidence_checkpoint,
        requested_start=history.requested_start,
        requested_end=history.requested_end,
        effective_start=history.effective_start,
        effective_end=history.effective_end,
        references=normalized_references,
        input_record_count=history.input_record_count,
        selected_record_count=history.selected_record_count,
        analyzed_record_count=history.analyzed_record_count,
        length_summaries=tuple(summaries),
        transformations=transformations,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )
