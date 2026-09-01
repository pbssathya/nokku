import pytest

from banyan.decimal_baselines import analyze_decimal_structural_baseline


def _metrics(result):
    return {
        (item.metric, item.reference_value): item
        for item in result.metrics
    }


def test_four_digit_baseline_reports_exact_space_assumptions_and_rates():
    result = analyze_decimal_structural_baseline(
        digit_length=4,
        reference_values=(3, 0),
    )

    assert result.status == "success"
    assert result.contract == "banyan.decimal_structural_baseline.v1"
    assert result.digit_length == 4
    assert result.space_size == 10_000
    assert result.reference_values == (3, 0)
    assert result.failures == ()
    assert result.uncertainty == ()
    assert any("leading zeros are allowed" in item for item in result.assumptions)
    assert any("not an assertion" in item for item in result.assumptions)

    metrics = _metrics(result)

    root_three = metrics[("digital_root_match", 3)]
    assert root_three.expected_count == 1111
    assert root_three.expected_rate == pytest.approx(0.1111)

    root_zero = metrics[("digital_root_match", 0)]
    assert root_zero.expected_count == 1
    assert root_zero.expected_rate == pytest.approx(0.0001)

    repeated_three = metrics[("reference_digit_repeated", 3)]
    assert repeated_three.expected_count == 523
    assert repeated_three.expected_rate == pytest.approx(0.0523)

    last_three = metrics[("last_digit_match", 3)]
    assert last_three.expected_count == 1000
    assert last_three.expected_rate == pytest.approx(0.1)


def test_repeated_digit_expectation_is_derived_for_five_and_six_digits():
    five = analyze_decimal_structural_baseline(
        digit_length=5,
        reference_values=(8,),
    )
    six = analyze_decimal_structural_baseline(
        digit_length=6,
        reference_values=(8,),
    )

    five_metric = _metrics(five)[("reference_digit_repeated", 8)]
    six_metric = _metrics(six)[("reference_digit_repeated", 8)]

    assert five.space_size == 100_000
    assert five_metric.expected_count == 8146
    assert five_metric.expected_rate == pytest.approx(0.08146)

    assert six.space_size == 1_000_000
    assert six_metric.expected_count == 114265
    assert six_metric.expected_rate == pytest.approx(0.114265)


def test_nonzero_digital_roots_are_symmetric_but_root_zero_is_not():
    result = analyze_decimal_structural_baseline(
        digit_length=6,
        reference_values=tuple(range(10)),
    )
    metrics = _metrics(result)

    nonzero_counts = {
        metrics[("digital_root_match", value)].expected_count
        for value in range(1, 10)
    }

    assert nonzero_counts == {111111}
    assert metrics[("digital_root_match", 0)].expected_count == 1
    assert metrics[("digital_root_match", 9)].expected_rate == pytest.approx(0.111111)
    assert metrics[("digital_root_match", 0)].expected_rate == pytest.approx(0.000001)


def test_last_digit_and_repeat_expectations_are_reference_digit_symmetric():
    result = analyze_decimal_structural_baseline(
        digit_length=6,
        reference_values=(0, 3, 8, 9),
    )
    metrics = _metrics(result)

    assert {
        metrics[("last_digit_match", value)].expected_count
        for value in (0, 3, 8, 9)
    } == {100_000}
    assert {
        metrics[("reference_digit_repeated", value)].expected_count
        for value in (0, 3, 8, 9)
    } == {114265}


def test_one_digit_space_handles_root_zero_and_zero_repeat_truthfully():
    result = analyze_decimal_structural_baseline(
        digit_length=1,
        reference_values=(0, 7),
    )
    metrics = _metrics(result)

    assert result.space_size == 10
    assert metrics[("digital_root_match", 0)].expected_count == 1
    assert metrics[("digital_root_match", 7)].expected_count == 1
    assert metrics[("last_digit_match", 0)].expected_count == 1
    assert metrics[("last_digit_match", 7)].expected_count == 1
    assert metrics[("reference_digit_repeated", 0)].expected_count == 0
    assert metrics[("reference_digit_repeated", 7)].expected_count == 0


def test_transformations_state_closed_form_non_enumerating_control():
    result = analyze_decimal_structural_baseline(
        digit_length=6,
        reference_values=(3,),
    )

    assert any("without enumerating" in item for item in result.transformations)
    assert any("all-zero root-0" in item for item in result.transformations)


def test_contract_rejects_invalid_lengths_and_reference_digits():
    for invalid_length in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="positive integer"):
            analyze_decimal_structural_baseline(
                digit_length=invalid_length,
                reference_values=(3,),
            )

    with pytest.raises(ValueError, match="at least one"):
        analyze_decimal_structural_baseline(
            digit_length=4,
            reference_values=(),
        )

    for invalid_reference in (-1, 10, True, 3.5):
        with pytest.raises(ValueError, match="0 to 9"):
            analyze_decimal_structural_baseline(
                digit_length=4,
                reference_values=(invalid_reference,),
            )

    with pytest.raises(ValueError, match="duplicate"):
        analyze_decimal_structural_baseline(
            digit_length=4,
            reference_values=(3, 3),
        )
