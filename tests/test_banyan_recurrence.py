import pytest

from banyan.recurrence import validate_finite_space_recurrence


def test_finite_space_recurrence_reports_observed_and_expected_values():
    result = validate_finite_space_recurrence(
        ("a", "a", "b", "c"),
        ("a", "d", "d"),
        space_size=4,
    )

    assert result.status == "success"
    assert result.contract == "banyan.finite_space_recurrence.v1"
    assert result.discovery.sample_size == 4
    assert result.discovery.distinct_value_count == 3
    assert result.discovery.recurring_value_count == 1
    assert result.discovery.repeat_occurrence_count == 1
    assert result.discovery.expected_distinct_value_count == pytest.approx(2.734375)
    assert result.discovery.expected_recurring_value_count == pytest.approx(1.046875)
    assert result.discovery.expected_repeat_occurrence_count == pytest.approx(1.265625)

    assert result.persistence.frozen_candidate_count == 1
    assert result.persistence.surviving_values == ("a",)
    assert result.persistence.observed_surviving_candidate_count == 1
    assert result.persistence.expected_surviving_candidate_count == pytest.approx(37 / 64)
    assert len(result.assumptions) == 3


def test_validation_recurrence_cannot_create_discovery_candidates():
    result = validate_finite_space_recurrence(
        ("a", "b"),
        ("c", "c", "c"),
        space_size=10,
    )

    assert result.discovery.recurring_value_count == 0
    assert result.validation.recurring_value_count == 1
    assert result.persistence.frozen_candidate_count == 0
    assert result.persistence.observed_surviving_candidate_count == 0
    assert result.persistence.surviving_values == ()


def test_space_size_is_caller_supplied_and_changes_only_the_control():
    small_space = validate_finite_space_recurrence(
        ("x", "x"),
        (),
        space_size=2,
    )
    large_space = validate_finite_space_recurrence(
        ("x", "x"),
        (),
        space_size=100,
    )

    assert small_space.discovery.recurring_value_count == 1
    assert large_space.discovery.recurring_value_count == 1
    assert small_space.discovery.expected_recurring_value_count != pytest.approx(
        large_space.discovery.expected_recurring_value_count
    )


def test_empty_cohorts_return_truthful_zero_receipt():
    result = validate_finite_space_recurrence((), (), space_size=100)

    assert result.status == "success"
    assert result.discovery.sample_size == 0
    assert result.validation.sample_size == 0
    assert result.combined.sample_size == 0
    assert result.discovery.distinct_value_count == 0
    assert result.discovery.recurring_value_count == 0
    assert result.discovery.expected_recurring_value_count == pytest.approx(0.0)
    assert result.discovery.recurring_value_ratio_to_expected is None
    assert result.persistence.expected_surviving_candidate_count == pytest.approx(0.0)
    assert result.persistence.survival_ratio_to_expected is None


def test_invalid_contract_inputs_are_rejected():
    with pytest.raises(ValueError, match="space_size"):
        validate_finite_space_recurrence(("a",), (), space_size=0)

    with pytest.raises(ValueError, match="non-empty strings"):
        validate_finite_space_recurrence(("",), (), space_size=10)
