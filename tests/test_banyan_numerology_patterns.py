import pytest

from banyan.numerology import NumberPatternObservation, observe_number


def test_observe_number_reports_generic_digit_structure():
    observation = observe_number("789430")

    assert isinstance(observation, NumberPatternObservation)
    assert observation.original == "789430"
    assert observation.digits == (7, 8, 9, 4, 3, 0)
    assert observation.digit_sum == 31
    assert observation.digital_root == 4
    assert observation.last_digit == "0"
    assert observation.last_two == "30"
    assert observation.last_three == "430"
    assert observation.last_four == "9430"
    assert observation.digit_frequency == (1, 0, 0, 1, 1, 0, 0, 1, 1, 1)
    assert observation.repeated_digits == ()


def test_observe_number_preserves_leading_zeroes_and_repetitions():
    observation = observe_number("003369")

    assert observation.original == "003369"
    assert observation.last_four == "3369"
    assert observation.digit_frequency[0] == 2
    assert observation.digit_frequency[3] == 2
    assert observation.repeated_digits == (0, 3)


def test_observe_number_rejects_non_numeric_input():
    with pytest.raises(ValueError, match="digits only"):
        observe_number("AB-123")
