from banyan.numerology import (
    BaselineRate,
    HistoricalNumerologySample,
    NumerologyReference,
    analyze_history,
)


def _refs() -> tuple[NumerologyReference, ...]:
    return (
        NumerologyReference("birth_number", 3),
        NumerologyReference("life_path", 9),
    )


def test_historical_analysis_reports_sample_counts_and_preserves_groups():
    summary = analyze_history(
        (
            HistoricalNumerologySample("39", _refs(), group="high"),
            HistoricalNumerologySample("33", _refs(), group="high"),
            HistoricalNumerologySample("18", _refs(), group="lower"),
        )
    )

    assert summary.sample_size == 3
    assert {item.group: item.sample_size for item in summary.groups} == {
        "high": 2,
        "lower": 1,
    }

    metrics = {(item.metric, item.reference_label): item for item in summary.metrics}
    assert metrics[("digital_root_match", "birth_number")].observed_count == 1
    assert metrics[("digital_root_match", "birth_number")].sample_size == 3
    assert metrics[("reference_digit_present", "birth_number")].observed_count == 2
    assert metrics[("reference_digit_repeated", "birth_number")].observed_count == 1
    assert metrics[("last_digit_match", "birth_number")].observed_count == 1


def test_historical_analysis_uses_only_explicit_caller_supplied_baseline():
    summary = analyze_history(
        (
            HistoricalNumerologySample("39", _refs()),
            HistoricalNumerologySample("33", _refs()),
            HistoricalNumerologySample("18", _refs()),
        ),
        baselines=(
            BaselineRate(
                metric="digital_root_match",
                reference_label="birth_number",
                expected_rate=1 / 9,
            ),
        ),
    )

    metrics = {(item.metric, item.reference_label): item for item in summary.metrics}
    metric = metrics[("digital_root_match", "birth_number")]

    assert metric.observed_rate == 1 / 3
    assert metric.baseline_rate == 1 / 9
    assert metric.delta_from_baseline == (1 / 3) - (1 / 9)

    no_baseline = metrics[("digital_root_match", "life_path")]
    assert no_baseline.baseline_rate is None
    assert no_baseline.delta_from_baseline is None


def test_group_specific_baseline_does_not_leak_into_other_groups():
    summary = analyze_history(
        (
            HistoricalNumerologySample("39", _refs(), group="high"),
            HistoricalNumerologySample("33", _refs(), group="high"),
            HistoricalNumerologySample("18", _refs(), group="lower"),
        ),
        baselines=(
            BaselineRate(
                metric="digital_root_match",
                reference_label="birth_number",
                expected_rate=0.25,
                group="high",
            ),
        ),
    )

    groups = {item.group: item for item in summary.groups}
    high_metrics = {
        (item.metric, item.reference_label): item for item in groups["high"].metrics
    }
    lower_metrics = {
        (item.metric, item.reference_label): item for item in groups["lower"].metrics
    }

    assert high_metrics[("digital_root_match", "birth_number")].baseline_rate == 0.25
    assert lower_metrics[("digital_root_match", "birth_number")].baseline_rate is None
