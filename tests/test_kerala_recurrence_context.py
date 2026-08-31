from datetime import date

import pytest

from nokku.lottery.kerala.recurrence_context import validate_context_recurrence
from nokku.lottery.kerala.winning_patterns import WinningNumberPattern


def _pattern(
    *,
    source: str,
    draw_date: date,
    numeric_part: str,
    lottery_code: str | None = "KR",
    tiers: tuple[str, ...] = ("3rd Prize",),
) -> WinningNumberPattern:
    return WinningNumberPattern(
        source=source,
        draw_serial=int(source) if source.isdigit() else None,
        draw_date=draw_date,
        lottery_name="TEST DRAW",
        lottery_code=lottery_code,
        numeric_part=numeric_part,
        ticket_occurrence_count=1,
        raw_prize_tiers=tiers,
        canonical_prize_tiers=tiers,
        prize_amounts=(100000,),
        series=("KA",),
        includes_first_prize="1st Prize" in tiers,
        includes_consolation="Consolation Prize" in tiers,
    )


def test_prize_tier_context_preserves_multi_tier_provenance():
    patterns = (
        _pattern(
            source="1",
            draw_date=date(2024, 1, 1),
            numeric_part="111111",
            tiers=("1st Prize", "Consolation Prize"),
        ),
        _pattern(
            source="2",
            draw_date=date(2025, 1, 1),
            numeric_part="111111",
            tiers=("1st Prize", "Consolation Prize"),
        ),
    )

    result = validate_context_recurrence(
        patterns,
        context_kind="prize_tier",
        digit_length=6,
        discovery_end=date(2024, 12, 31),
        validation_start=date(2025, 1, 1),
        evidence_checkpoint="fixture:tiers",
    )

    assert result.status == "success"
    assert result.contract == "kerala.context_recurrence.v1"
    assert result.number_space_size == 1_000_000
    assert [group.context_value for group in result.groups] == [
        "1st Prize",
        "Consolation Prize",
    ]
    for group in result.groups:
        assert group.discovery_pattern_count == 1
        assert group.validation_pattern_count == 1
        assert group.analysis.discovery.sample_size == 1
        assert group.analysis.validation.sample_size == 1


def test_lottery_code_contexts_have_independent_sample_sizes_and_baselines():
    patterns = (
        _pattern(source="1", draw_date=date(2024, 1, 1), numeric_part="111111", lottery_code="AK"),
        _pattern(source="2", draw_date=date(2024, 2, 1), numeric_part="111111", lottery_code="AK"),
        _pattern(source="3", draw_date=date(2024, 3, 1), numeric_part="222222", lottery_code="AK"),
        _pattern(source="4", draw_date=date(2024, 4, 1), numeric_part="333333", lottery_code="KR"),
        _pattern(source="5", draw_date=date(2025, 1, 1), numeric_part="111111", lottery_code="AK"),
        _pattern(source="6", draw_date=date(2025, 2, 1), numeric_part="444444", lottery_code="KR"),
    )

    result = validate_context_recurrence(
        patterns,
        context_kind="lottery_code",
        digit_length=6,
        discovery_end=date(2024, 12, 31),
        validation_start=date(2025, 1, 1),
        evidence_checkpoint="fixture:codes",
    )

    groups = {group.context_value: group for group in result.groups}
    assert set(groups) == {"AK", "KR"}
    assert groups["AK"].discovery_pattern_count == 3
    assert groups["AK"].validation_pattern_count == 1
    assert groups["AK"].analysis.discovery.recurring_value_count == 1
    assert groups["AK"].analysis.persistence.surviving_values == ("111111",)

    assert groups["KR"].discovery_pattern_count == 1
    assert groups["KR"].validation_pattern_count == 1
    assert groups["AK"].analysis.discovery.expected_recurring_value_count != pytest.approx(
        groups["KR"].analysis.discovery.expected_recurring_value_count
    )


def test_missing_lottery_code_is_reported_as_uncertainty_not_invented_context():
    patterns = (
        _pattern(
            source="1",
            draw_date=date(2024, 1, 1),
            numeric_part="111111",
            lottery_code=None,
        ),
    )

    result = validate_context_recurrence(
        patterns,
        context_kind="lottery_code",
        digit_length=6,
        discovery_end=date(2024, 12, 31),
        validation_start=date(2025, 1, 1),
        evidence_checkpoint="fixture:missing-code",
    )

    assert result.status == "partial"
    assert result.groups == ()
    assert len(result.uncertainty) == 1
    assert "no usable context value" in result.uncertainty[0]


def test_context_adapter_reports_date_gap_without_forcing_assignment():
    patterns = (
        _pattern(source="1", draw_date=date(2024, 12, 31), numeric_part="111111"),
        _pattern(source="2", draw_date=date(2025, 1, 15), numeric_part="222222"),
        _pattern(source="3", draw_date=date(2025, 2, 1), numeric_part="333333"),
    )

    result = validate_context_recurrence(
        patterns,
        context_kind="lottery_code",
        digit_length=6,
        discovery_end=date(2024, 12, 31),
        validation_start=date(2025, 2, 1),
        evidence_checkpoint="fixture:gap",
    )

    assert result.unassigned_pattern_count == 1
    assert result.groups[0].discovery_pattern_count == 1
    assert result.groups[0].validation_pattern_count == 1


def test_context_adapter_rejects_invalid_contract_inputs():
    with pytest.raises(ValueError, match="context_kind"):
        validate_context_recurrence(
            (),
            context_kind="weekday",  # type: ignore[arg-type]
            digit_length=6,
            discovery_end=date(2024, 12, 31),
            validation_start=date(2025, 1, 1),
            evidence_checkpoint="fixture",
        )

    with pytest.raises(ValueError, match="digit_length"):
        validate_context_recurrence(
            (),
            context_kind="lottery_code",
            digit_length=0,
            discovery_end=date(2024, 12, 31),
            validation_start=date(2025, 1, 1),
            evidence_checkpoint="fixture",
        )

    with pytest.raises(ValueError, match="validation_start"):
        validate_context_recurrence(
            (),
            context_kind="prize_tier",
            digit_length=6,
            discovery_end=date(2025, 1, 1),
            validation_start=date(2025, 1, 1),
            evidence_checkpoint="fixture",
        )

    with pytest.raises(ValueError, match="evidence_checkpoint"):
        validate_context_recurrence(
            (),
            context_kind="lottery_code",
            digit_length=6,
            discovery_end=date(2024, 12, 31),
            validation_start=date(2025, 1, 1),
            evidence_checkpoint="   ",
        )
