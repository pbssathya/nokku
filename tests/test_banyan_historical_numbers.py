from datetime import date

import pytest

from banyan.historical_numbers import (
    HistoricalNumberRecord,
    analyze_historical_numbers,
)


def _record(value: int | str, observed_on: date, source: str = "") -> HistoricalNumberRecord:
    return HistoricalNumberRecord(value=value, observed_on=observed_on, source=source)


def test_analysis_filters_range_and_preserves_lineage_receipt():
    records = (
        _record("1111", date(2023, 12, 31), "before"),
        _record("1234", date(2024, 1, 1), "start"),
        _record("5678", date(2024, 6, 1), "middle"),
        _record("9999", date(2024, 12, 31), "end"),
        _record("0000", date(2025, 1, 1), "after"),
    )

    result = analyze_historical_numbers(
        records,
        evidence_checkpoint="fixture:range",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        ending_widths=(1, 2),
    )

    assert result.status == "success"
    assert result.contract == "banyan.historical_numbers.v1"
    assert result.evidence_checkpoint == "fixture:range"
    assert result.requested_start == date(2024, 1, 1)
    assert result.requested_end == date(2024, 12, 31)
    assert result.effective_start == date(2024, 1, 1)
    assert result.effective_end == date(2024, 12, 31)
    assert result.input_record_count == 5
    assert result.selected_record_count == 3
    assert result.analyzed_record_count == 3
    assert result.excluded_by_range_count == 2
    assert result.ending_widths == (1, 2)
    assert result.failures == ()
    assert result.uncertainty == ()


def test_numeric_lengths_are_never_mixed():
    records = (
        _record("1234", date(2024, 1, 1)),
        _record("1234", date(2024, 2, 1)),
        _record("001234", date(2024, 3, 1)),
        _record("001234", date(2024, 4, 1)),
    )

    result = analyze_historical_numbers(
        records,
        evidence_checkpoint="fixture:lengths",
        ending_widths=(1, 2, 4, 6),
    )

    summaries = {summary.digit_length: summary for summary in result.length_summaries}
    assert set(summaries) == {4, 6}
    assert summaries[4].sample_size == 2
    assert summaries[6].sample_size == 2
    assert summaries[4].exact_recurrences[0].value == "1234"
    assert summaries[4].exact_recurrences[0].occurrence_count == 2
    assert summaries[6].exact_recurrences[0].value == "001234"
    assert summaries[6].exact_recurrences[0].occurrence_count == 2
    assert {item.width for item in summaries[4].ending_counts} == {1, 2, 4}
    assert {item.width for item in summaries[6].ending_counts} == {1, 2, 4, 6}


def test_analysis_reuses_number_structure_for_roots_endings_and_repeated_digits():
    records = (
        _record("1123", date(2024, 1, 1)),
        _record("4445", date(2024, 1, 2)),
    )

    result = analyze_historical_numbers(
        records,
        evidence_checkpoint="fixture:structure",
        ending_widths=(1, 2),
    )

    summary = result.length_summaries[0]
    # 1+1+2+3 = 7; 4+4+4+5 = 17 -> 8
    assert summary.digital_root_counts == ((7, 1), (8, 1))
    assert summary.repeated_digit_counts == ((1, 1), (4, 1))

    endings = {(item.width, item.ending): item for item in summary.ending_counts}
    assert endings[(1, "3")].observed_count == 1
    assert endings[(1, "5")].observed_count == 1
    assert endings[(2, "23")].observed_rate == pytest.approx(0.5)
    assert endings[(2, "45")].observed_rate == pytest.approx(0.5)


def test_exact_recurrence_is_descriptive_and_preserves_first_last_dates():
    records = (
        _record("654321", date(2020, 1, 1)),
        _record("123456", date(2021, 1, 1)),
        _record("654321", date(2022, 1, 1)),
        _record("654321", date(2023, 1, 1)),
    )

    result = analyze_historical_numbers(
        records,
        evidence_checkpoint="fixture:recurrence",
    )

    recurrence = result.length_summaries[0].exact_recurrences
    assert len(recurrence) == 1
    assert recurrence[0].value == "654321"
    assert recurrence[0].occurrence_count == 3
    assert recurrence[0].first_seen == date(2020, 1, 1)
    assert recurrence[0].last_seen == date(2023, 1, 1)
    assert any("without finite-space expectation" in item for item in result.transformations)


def test_invalid_number_is_reported_without_discarding_valid_records():
    records = (
        _record("1234", date(2024, 1, 1), "good"),
        _record("12A4", date(2024, 1, 2), "bad-source"),
    )

    result = analyze_historical_numbers(
        records,
        evidence_checkpoint="fixture:partial",
        ending_widths=(1,),
    )

    assert result.status == "partial"
    assert result.selected_record_count == 2
    assert result.analyzed_record_count == 1
    assert len(result.failures) == 1
    assert "bad-source" in result.failures[0]
    assert "12A4" in result.failures[0]
    assert result.length_summaries[0].sample_size == 1


def test_empty_selected_range_is_truthful_success_when_no_records_are_selected():
    records = (_record("1234", date(2024, 1, 1)),)

    result = analyze_historical_numbers(
        records,
        evidence_checkpoint="fixture:empty-range",
        start=date(2025, 1, 1),
        end=date(2025, 12, 31),
    )

    assert result.status == "success"
    assert result.selected_record_count == 0
    assert result.analyzed_record_count == 0
    assert result.effective_start is None
    assert result.effective_end is None
    assert result.length_summaries == ()


def test_selected_but_unanalyzable_range_reports_uncertainty():
    records = (_record("NOT-A-NUMBER", date(2024, 1, 1), "bad"),)

    result = analyze_historical_numbers(
        records,
        evidence_checkpoint="fixture:none-analyzable",
    )

    assert result.status == "partial"
    assert result.selected_record_count == 1
    assert result.analyzed_record_count == 0
    assert len(result.failures) == 1
    assert result.uncertainty == (
        "selected range contains no analyzable numeric observations",
    )


def test_contract_rejects_invalid_checkpoint_range_and_ending_widths():
    with pytest.raises(ValueError, match="evidence_checkpoint"):
        analyze_historical_numbers((), evidence_checkpoint="   ")

    with pytest.raises(ValueError, match="start"):
        analyze_historical_numbers(
            (),
            evidence_checkpoint="fixture",
            start=date(2025, 1, 1),
            end=date(2024, 1, 1),
        )

    with pytest.raises(ValueError, match="positive integers"):
        analyze_historical_numbers(
            (),
            evidence_checkpoint="fixture",
            ending_widths=(0,),
        )

    with pytest.raises(ValueError, match="duplicates"):
        analyze_historical_numbers(
            (),
            evidence_checkpoint="fixture",
            ending_widths=(2, 2),
        )
