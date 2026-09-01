from dataclasses import replace
from datetime import date

import pytest

from banyan.anonymous_numerology import (
    AnonymousNumerologyBaseline,
    analyze_anonymous_historical_numerology,
)
from banyan.historical_numbers import HistoricalNumberRecord, analyze_historical_numbers
from banyan.numerology import NumerologyReference


def _history(*, ending_widths=(1,)):
    return analyze_historical_numbers(
        (
            HistoricalNumberRecord("3300", date(2024, 1, 1), "a"),
            HistoricalNumberRecord("1233", date(2024, 1, 2), "b"),
            HistoricalNumberRecord("9993", date(2024, 1, 3), "c"),
        ),
        evidence_checkpoint="fixture:anonymous",
        start=date(2024, 1, 1),
        end=date(2024, 1, 3),
        ending_widths=ending_widths,
    )


def _metric_lookup(result):
    summary = result.length_summaries[0]
    return {
        (item.metric, item.reference_label): item
        for item in summary.metrics
    }


def test_anonymous_numerology_uses_only_upstream_snapshot_facts():
    history = _history()
    result = analyze_anonymous_historical_numerology(
        history,
        references=(
            NumerologyReference("target_root", 3),
            NumerologyReference("draw_root", 9),
        ),
    )

    assert result.status == "success"
    assert result.contract == "banyan.anonymous_historical_numerology.v1"
    assert result.upstream_contract == "banyan.historical_numbers.v1"
    assert result.evidence_checkpoint == "fixture:anonymous"

    metrics = _metric_lookup(result)

    # 9993 has digital root 3; 1233 has digital root 9.
    assert metrics[("digital_root_match", "target_root")].observed_count == 1
    assert metrics[("digital_root_match", "draw_root")].observed_count == 1

    # Digit 3 repeats in 3300 and 1233; digit 9 repeats only in 9993.
    assert metrics[("reference_digit_repeated", "target_root")].observed_count == 2
    assert metrics[("reference_digit_repeated", "draw_root")].observed_count == 1

    # Two values end in 3; none ends in 9.
    assert metrics[("last_digit_match", "target_root")].observed_count == 2
    assert metrics[("last_digit_match", "draw_root")].observed_count == 0

    assert all(
        item.metric != "reference_digit_present"
        for summary in result.length_summaries
        for item in summary.metrics
    )
    assert any("without rereading raw historical observations" in item for item in result.transformations)


def test_lineage_and_numeric_length_boundaries_flow_from_upstream_receipt():
    history = analyze_historical_numbers(
        (
            HistoricalNumberRecord("1234", date(2020, 1, 1), "four"),
            HistoricalNumberRecord("001234", date(2021, 1, 1), "six"),
        ),
        evidence_checkpoint="fixture:length-lineage",
        start=date(2020, 1, 1),
        end=date(2021, 1, 1),
        ending_widths=(1,),
    )

    result = analyze_anonymous_historical_numerology(
        history,
        references=(NumerologyReference("target_root", 1),),
    )

    assert result.evidence_checkpoint == history.evidence_checkpoint
    assert result.requested_start == history.requested_start
    assert result.requested_end == history.requested_end
    assert result.effective_start == history.effective_start
    assert result.effective_end == history.effective_end
    assert result.input_record_count == history.input_record_count
    assert result.selected_record_count == history.selected_record_count
    assert result.analyzed_record_count == history.analyzed_record_count
    assert [(item.digit_length, item.sample_size) for item in result.length_summaries] == [
        (4, 1),
        (6, 1),
    ]


def test_explicit_baseline_is_applied_without_inventing_other_baselines():
    history = _history()
    result = analyze_anonymous_historical_numerology(
        history,
        references=(NumerologyReference("target_root", 3),),
        baselines=(
            AnonymousNumerologyBaseline(
                digit_length=4,
                metric="digital_root_match",
                reference_label="target_root",
                expected_rate=1 / 9,
            ),
        ),
    )

    metrics = _metric_lookup(result)
    root_metric = metrics[("digital_root_match", "target_root")]
    repeat_metric = metrics[("reference_digit_repeated", "target_root")]

    assert root_metric.observed_rate == pytest.approx(1 / 3)
    assert root_metric.baseline_rate == pytest.approx(1 / 9)
    assert root_metric.delta_from_baseline == pytest.approx((1 / 3) - (1 / 9))
    assert repeat_metric.baseline_rate is None
    assert repeat_metric.delta_from_baseline is None


def test_missing_width_one_evidence_is_reported_without_fabricating_last_digit_metric():
    history = _history(ending_widths=(2,))
    result = analyze_anonymous_historical_numerology(
        history,
        references=(NumerologyReference("target_root", 3),),
    )

    assert result.status == "partial"
    metrics = _metric_lookup(result)
    assert ("digital_root_match", "target_root") in metrics
    assert ("reference_digit_repeated", "target_root") in metrics
    assert ("last_digit_match", "target_root") not in metrics
    assert len(result.uncertainty) == 1
    assert "omitted ending width 1" in result.uncertainty[0]


def test_upstream_failures_are_preserved_in_anonymous_receipt():
    history = analyze_historical_numbers(
        (
            HistoricalNumberRecord("1234", date(2024, 1, 1), "good"),
            HistoricalNumberRecord("12A4", date(2024, 1, 2), "bad"),
        ),
        evidence_checkpoint="fixture:partial-upstream",
        ending_widths=(1,),
    )
    assert history.status == "partial"

    result = analyze_anonymous_historical_numerology(
        history,
        references=(NumerologyReference("target_root", 3),),
    )

    assert result.status == "partial"
    assert result.failures == history.failures
    assert result.analyzed_record_count == 1


def test_contract_rejects_invalid_references_baselines_and_upstream_contract():
    history = _history()

    with pytest.raises(ValueError, match="at least one"):
        analyze_anonymous_historical_numerology(history, references=())

    with pytest.raises(ValueError, match="duplicate"):
        analyze_anonymous_historical_numerology(
            history,
            references=(
                NumerologyReference("same", 3),
                NumerologyReference("same", 9),
            ),
        )

    with pytest.raises(ValueError, match="0 to 9"):
        analyze_anonymous_historical_numerology(
            history,
            references=(NumerologyReference("bad", 10),),
        )

    with pytest.raises(ValueError, match="unsupported"):
        analyze_anonymous_historical_numerology(
            history,
            references=(NumerologyReference("target_root", 3),),
            baselines=(
                AnonymousNumerologyBaseline(
                    digit_length=4,
                    metric="reference_digit_present",
                    reference_label="target_root",
                    expected_rate=0.5,
                ),
            ),
        )

    with pytest.raises(ValueError, match="unknown label"):
        analyze_anonymous_historical_numerology(
            history,
            references=(NumerologyReference("target_root", 3),),
            baselines=(
                AnonymousNumerologyBaseline(
                    digit_length=4,
                    metric="digital_root_match",
                    reference_label="other",
                    expected_rate=0.5,
                ),
            ),
        )

    with pytest.raises(ValueError, match="between 0 and 1"):
        analyze_anonymous_historical_numerology(
            history,
            references=(NumerologyReference("target_root", 3),),
            baselines=(
                AnonymousNumerologyBaseline(
                    digit_length=4,
                    metric="digital_root_match",
                    reference_label="target_root",
                    expected_rate=1.1,
                ),
            ),
        )

    incompatible = replace(history, contract="other.contract.v1")
    with pytest.raises(ValueError, match="historical_numbers.v1"):
        analyze_anonymous_historical_numerology(
            incompatible,
            references=(NumerologyReference("target_root", 3),),
        )
