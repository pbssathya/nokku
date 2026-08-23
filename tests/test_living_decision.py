from datetime import date, datetime, timezone

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from cossse.memory import Memory

from nokku.lottery.kerala.living import kerala_today, run_weekly_decision


def test_kerala_today_uses_ist_not_codespace_utc():
    utc_late_evening = datetime(2026, 8, 23, 20, 0, tzinfo=timezone.utc)

    assert kerala_today(utc_late_evening) == date(2026, 8, 24)


def test_living_loop_preserves_decision_experience(tmp_path):
    memory_path = tmp_path / "living.sqlite"
    preferences_path = tmp_path / "preferences.json"

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 24),
        refresh=False,
        memory_path=memory_path,
        preferences_path=preferences_path,
    )

    assert result.decision.recommendation == "SKIP"
    assert result.refreshed_sources == ()

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    assert recalled["body"]["experience"] == "decision"
    assert recalled["body"]["application"] == "nokku"
    assert recalled["body"]["decision_type"] == "weekly_participation"
    assert recalled["body"]["decision"]["recommendation"] == "SKIP"


def test_living_loop_respects_explicit_buy(tmp_path):
    result = run_weekly_decision(
        "I want to buy this week",
        anchor=date(2026, 8, 24),
        refresh=False,
        memory_path=tmp_path / "living.sqlite",
        preferences_path=tmp_path / "preferences.json",
    )

    assert result.decision.recommendation == "BUY"
    assert result.decision.override == "BUY"
