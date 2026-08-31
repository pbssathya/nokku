from datetime import date

import pytest

from nokku.lottery.kerala.recurrence_validation import validate_numeric_length_recurrence
from nokku.lottery.kerala.winning_patterns import WinningNumberPattern


def _pattern(*, source: str, draw_date: date, numeric_part: str) -> WinningNumberPattern:
    return WinningNumberPattern(
        source=source,
        draw_serial=int(source) if source.isdigit() else None,
        draw_date=draw_date,
        lottery_name="TEST DRAW",
        lottery_code="KR",
        numeric_part=numeric_part,
        ticket_occurrence_count=1,
        raw_prize_tiers=("3rd Prize",),
        canonical_prize_tiers=("3rd Prize",),
        prize_amounts=(100000,),
        series=("KA",),
        includes_first_prize=False,
        includes_consolation=False,
    )


def test_kerala_adapter_derives_numeric_space_and_preserves_lineage():
    patterns = (
        _pattern(source="1", draw_date=date(2024, 1, 1), numeric_part="111111"),
        _pattern(source="2", draw_date=date(2024, 2, 1), numeric_part="111111"),
        _pattern(source="3", draw_date=date(2024, 3, 1), numeric_part="222222"),
        _pattern(source="4", draw_date=date(2025, 1, 1), numeric_part="111111"),
        _pattern(source="5", draw_date=date(2025, 2, 1), numeric_part="333333"),
        _pattern(source="6", draw_date=date(2025, 3, 1), numeric_part="333333"),
        _pattern(source="7", draw_date=date(2025, 3, 1), numeric_part="0042"),
    )

    result = validate_numeric_length_recurrence(
        patterns,
        digit_length=6,
        discovery_end=date(2024, 12, 31),
        validation_start=date(2025, 1, 1),
        evidence_checkpoint="fixture:2025-03-01",
    )

    assert result.status == "success"
    assert result.contract == "kerala.numeric_length_recurrence.v1"
    assert result.evidence_checkpoint == "fixture:2025-03-01"
    assert result.number_space_size == 1_000_000
    assert result.input_pattern_count == 7
    assert result.cohort_pattern_count == 6
    assert result.discovery_pattern_count == 3
    assert result.validation_pattern_count == 3
    assert result.unassigned_pattern_count == 0
    assert result.analysis.persistence.frozen_candidate_count == 1
    assert result.analysis.persistence.surviving_values == ("111111",)
    assert result.analysis.persistence.observed_surviving_candidate_count == 1
    assert result.analysis.validation.recurring_value_count == 1
    assert any("10**6=1000000" in item for item in result.transformations)


def test_adapter_allows_caller_defined_gap_and_reports_unassigned_patterns():
    patterns = (
        _pattern(source="1", draw_date=date(2024, 12, 31), numeric_part="111111"),
        _pattern(source="2", draw_date=date(2025, 1, 15), numeric_part="222222"),
        _pattern(source="3", draw_date=date(2025, 2, 1), numeric_part="333333"),
    )

    result = validate_numeric_length_recurrence(
        patterns,
        digit_length=6,
        discovery_end=date(2024, 12, 31),
        validation_start=date(2025, 2, 1),
        evidence_checkpoint="fixture:gap",
    )

    assert result.discovery_pattern_count == 1
    assert result.validation_pattern_count == 1
    assert result.unassigned_pattern_count == 1


def test_adapter_rejects_overlapping_or_missing_contract_inputs():
    with pytest.raises(ValueError, match="validation_start"):
        validate_numeric_length_recurrence(
            (),
            digit_length=6,
            discovery_end=date(2025, 1, 1),
            validation_start=date(2025, 1, 1),
            evidence_checkpoint="fixture",
        )

    with pytest.raises(ValueError, match="digit_length"):
        validate_numeric_length_recurrence(
            (),
            digit_length=0,
            discovery_end=date(2024, 12, 31),
            validation_start=date(2025, 1, 1),
            evidence_checkpoint="fixture",
        )

    with pytest.raises(ValueError, match="evidence_checkpoint"):
        validate_numeric_length_recurrence(
            (),
            digit_length=6,
            discovery_end=date(2024, 12, 31),
            validation_start=date(2025, 1, 1),
            evidence_checkpoint="   ",
        )
