from datetime import date

from nokku.lottery.kerala.decision import (
    KeralaLotteryFact,
    decide_weekly_participation,
    detect_user_override,
    resolve_week,
)


def test_friday_to_thursday_week_resolution():
    start, end = resolve_week(date(2026, 8, 24), "friday")

    assert start == date(2026, 8, 21)
    assert end == date(2026, 8, 27)


def test_neutral_request_defaults_to_skip_without_claiming_prediction():
    facts = (
        KeralaLotteryFact("1", date(2026, 8, 17), "TEST A"),
        KeralaLotteryFact("2", date(2026, 8, 18), "TEST B"),
    )

    decision = decide_weekly_participation(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 24),
        facts=facts,
        week_start_name="friday",
    )

    assert decision.recommendation == "SKIP"
    assert decision.override is None
    assert "random" in decision.uncertainty.lower()
    assert any("future edge" in item for item in decision.evidence_summary)


def test_explicit_buy_is_respected_as_user_override():
    decision = decide_weekly_participation(
        "I want to buy this week",
        anchor=date(2026, 8, 24),
        facts=(),
    )

    assert decision.recommendation == "BUY"
    assert decision.override == "BUY"


def test_explicit_skip_is_respected_as_user_override():
    decision = decide_weekly_participation(
        "Skip the lottery this week",
        anchor=date(2026, 8, 24),
        facts=(),
    )

    assert decision.recommendation == "SKIP"
    assert decision.override == "SKIP"


def test_question_word_buy_is_not_mistaken_for_override():
    assert detect_user_override("Should I buy this week?") is None
