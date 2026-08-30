from datetime import date

from nokku.lottery.kerala.historical_recurrence import analyze_historical_patterns
from nokku.lottery.kerala.winning_patterns import WinningNumberPattern


def _pattern(
    *,
    source: str,
    draw_date: date,
    lottery_code: str,
    numeric_part: str,
    tiers: tuple[str, ...],
) -> WinningNumberPattern:
    return WinningNumberPattern(
        source=source,
        draw_serial=int(source),
        draw_date=draw_date,
        lottery_name=f"{lottery_code} TEST DRAW",
        lottery_code=lottery_code,
        numeric_part=numeric_part,
        ticket_occurrence_count=1,
        raw_prize_tiers=tiers,
        canonical_prize_tiers=tiers,
        prize_amounts=(),
        series=(),
        includes_first_prize="1st Prize" in tiers,
        includes_consolation="Consolation Prize" in tiers,
    )


def test_anonymous_history_reports_recurrence_and_structure_without_scoring():
    result = analyze_historical_patterns(
        (
            _pattern(
                source="1",
                draw_date=date(2026, 8, 1),
                lottery_code="KR",
                numeric_part="1234",
                tiers=("1st Prize", "Consolation Prize"),
            ),
            _pattern(
                source="2",
                draw_date=date(2026, 8, 2),
                lottery_code="KR",
                numeric_part="1234",
                tiers=("7th Prize",),
            ),
            _pattern(
                source="3",
                draw_date=date(2026, 8, 3),
                lottery_code="SS",
                numeric_part="9234",
                tiers=("7th Prize",),
            ),
            _pattern(
                source="4",
                draw_date=date(2026, 8, 4),
                lottery_code="SS",
                numeric_part="7777",
                tiers=("8th Prize",),
            ),
        )
    )

    assert result.status == "success"
    assert result.sample_size == 4
    assert result.analyzed_sample_size == 4
    assert result.failures == ()
    assert result.uncertainty == ()

    assert dict(result.digital_root_counts) == {1: 3, 9: 1}
    assert dict(result.repeated_digit_counts) == {7: 1}
    assert dict(result.lottery_code_counts) == {"KR": 2, "SS": 2}
    assert dict(result.prize_tier_counts) == {
        "1st Prize": 1,
        "Consolation Prize": 1,
        "7th Prize": 2,
        "8th Prize": 1,
    }

    last_two = {
        item.ending: item.observed_count
        for item in result.ending_counts
        if item.width == 2
    }
    assert last_two == {"34": 3, "77": 1}

    assert len(result.exact_number_recurrences) == 1
    recurrence = result.exact_number_recurrences[0]
    assert recurrence.numeric_part == "1234"
    assert recurrence.occurrence_count == 2
    assert recurrence.first_seen == date(2026, 8, 1)
    assert recurrence.last_seen == date(2026, 8, 2)


def test_malformed_pattern_is_reported_without_hiding_valid_samples():
    result = analyze_historical_patterns(
        (
            _pattern(
                source="1",
                draw_date=date(2026, 8, 1),
                lottery_code="KR",
                numeric_part="1234",
                tiers=("7th Prize",),
            ),
            _pattern(
                source="2",
                draw_date=date(2026, 8, 2),
                lottery_code="KR",
                numeric_part="AB12",
                tiers=("7th Prize",),
            ),
        )
    )

    assert result.status == "partial"
    assert result.sample_size == 2
    assert result.analyzed_sample_size == 1
    assert len(result.failures) == 1
    assert "source=2" in result.failures[0]
    assert result.uncertainty == ()
