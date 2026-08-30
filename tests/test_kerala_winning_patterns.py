from datetime import date

from nokku.lottery.kerala.winning_corpus import WinningNumberEntry
from nokku.lottery.kerala.winning_patterns import (
    build_numeric_pattern_view,
    canonical_prize_tier,
)


def _entry(
    *,
    source: str,
    numeric_part: str,
    prize_tier: str,
    prize_amount: int,
    series: str | None,
) -> WinningNumberEntry:
    return WinningNumberEntry(
        source=source,
        draw_serial=int(source) if source.isdigit() else None,
        draw_date=date(2026, 8, 1),
        lottery_name="KARUNYA LOTTERY NO.KR-763rd DRAW",
        lottery_code="KR",
        prize_tier=prize_tier,
        prize_amount=prize_amount,
        series=series,
        full_number=f"{series} {numeric_part}" if series else numeric_part,
        numeric_part=numeric_part,
        raw_entry=f"{series} {numeric_part}" if series else numeric_part,
    )


def test_numeric_pattern_view_collapses_first_and_consolation_ticket_occurrences():
    entries = (
        _entry(
            source="75337",
            numeric_part="247228",
            prize_tier="1st Prize",
            prize_amount=10000000,
            series="KO",
        ),
        _entry(
            source="75337",
            numeric_part="247228",
            prize_tier="Cons Prize",
            prize_amount=5000,
            series="KN",
        ),
        _entry(
            source="75337",
            numeric_part="247228",
            prize_tier="Cons Prize",
            prize_amount=5000,
            series="KP",
        ),
        _entry(
            source="75337",
            numeric_part="0014",
            prize_tier="7th Prize",
            prize_amount=500,
            series=None,
        ),
    )

    result = build_numeric_pattern_view(entries)

    assert result.status == "success"
    assert result.ticket_entry_count == 4
    assert result.unique_pattern_count == 2
    assert result.collapsed_occurrence_count == 2

    pattern = result.patterns[0]
    assert pattern.numeric_part == "247228"
    assert pattern.ticket_occurrence_count == 3
    assert pattern.raw_prize_tiers == ("1st Prize", "Cons Prize")
    assert pattern.canonical_prize_tiers == ("1st Prize", "Consolation Prize")
    assert pattern.prize_amounts == (10000000, 5000)
    assert pattern.series == ("KO", "KN", "KP")
    assert pattern.includes_first_prize is True
    assert pattern.includes_consolation is True


def test_same_numeric_part_in_different_draws_remains_distinct():
    entries = (
        _entry(
            source="75337",
            numeric_part="247228",
            prize_tier="1st Prize",
            prize_amount=10000000,
            series="KO",
        ),
        _entry(
            source="75338",
            numeric_part="247228",
            prize_tier="2nd Prize",
            prize_amount=2500000,
            series="MZ",
        ),
    )

    result = build_numeric_pattern_view(entries)

    assert result.unique_pattern_count == 2
    assert [pattern.source for pattern in result.patterns] == ["75337", "75338"]


def test_consolation_labels_have_one_canonical_analytical_name():
    assert canonical_prize_tier("Cons Prize") == "Consolation Prize"
    assert canonical_prize_tier("Consolation Prize") == "Consolation Prize"
    assert canonical_prize_tier("1st Prize") == "1st Prize"
