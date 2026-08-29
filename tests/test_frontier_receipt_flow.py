from datetime import date

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from cossse.memory import Memory

from nokku.lottery.kerala import living
from nokku.lottery.kerala.living import (
    FrontierRefreshResult,
    ScheduleCollectionResult,
    run_weekly_decision,
)


def test_living_decision_preserves_frontier_refresh_failure_receipt(tmp_path, monkeypatch):
    frontier = FrontierRefreshResult(
        status="failed",
        refreshed_sources=(),
        attempted_sources=("75364",),
        checkpoint_source="75363",
        checkpoint_draw_date=date(2026, 8, 29),
        stop_reason="collector_execution_not_usable",
        failures=("source 75364 collector execution status: failed",),
        uncertainty=(),
    )
    schedule = ScheduleCollectionResult(
        status="success",
        dates=(),
        draw_numbers={},
        disposition_status="claimed",
        execution_status="success",
    )

    monkeypatch.setattr(
        living,
        "refresh_current_frontier_result",
        lambda **_kwargs: frontier,
    )
    monkeypatch.setattr(
        living,
        "collect_upcoming_draw_schedule",
        lambda **_kwargs: schedule,
    )

    memory_path = tmp_path / "living.sqlite"
    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 30),
        refresh=True,
        memory_path=memory_path,
        preferences_path=tmp_path / "preferences.json",
    )

    assert result.frontier_refresh is frontier
    assert result.refreshed_sources == ()
    assert result.decision.recommendation == "SKIP"

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    receipt = recalled["body"]["operational_context"]["current_result_frontier_refresh"]
    assert receipt == {
        "status": "failed",
        "checkpoint_source": "75363",
        "checkpoint_draw_date": "2026-08-29",
        "attempted_sources": ["75364"],
        "refreshed_sources": [],
        "stop_reason": "collector_execution_not_usable",
        "failures": ["source 75364 collector execution status: failed"],
        "uncertainty": [],
    }


def test_living_decision_records_frontier_not_requested_when_refresh_disabled(tmp_path):
    memory_path = tmp_path / "living.sqlite"
    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 30),
        refresh=False,
        memory_path=memory_path,
        preferences_path=tmp_path / "preferences.json",
    )

    assert result.frontier_refresh is None

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    receipt = recalled["body"]["operational_context"]["current_result_frontier_refresh"]
    assert receipt == {"status": "not_requested"}
