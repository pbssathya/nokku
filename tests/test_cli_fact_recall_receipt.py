from argparse import Namespace
from datetime import date
from types import SimpleNamespace

from nokku import __main__ as cli
from nokku.memory_flow import MemoryPreservationResult


def _args() -> Namespace:
    return Namespace(
        request="Should I buy a Kerala lottery this week?",
        anchor_date="2026-08-29",
        user_timezone=None,
        remember_timezone=False,
        week_start=None,
        remember_week_start=False,
        astrology_at=None,
        natal_moon_longitude=None,
        no_refresh=True,
    )


def _decision_result() -> SimpleNamespace:
    decision = SimpleNamespace(
        recommendation="SKIP",
        week_start=date(2026, 8, 28),
        week_end=date(2026, 9, 3),
        preferred_date=None,
        backup_date=None,
        preferred_time="NONE",
        override=None,
        evidence_summary=("test evidence",),
        uncertainty="test uncertainty",
    )
    preservation = MemoryPreservationResult(
        status="success",
        memory_id="decision-1",
        disposition_status="claimed",
        feedback_count=1,
        memory_event="preserved",
    )
    memory_discovery = SimpleNamespace(
        status="failed",
        discovered_receipt_count=0,
        attempted_memory_ids=(),
        discovery_disposition_status="unclaimed",
        failures=("memory discovery unavailable",),
        uncertainty=("no discovery receipt was returned",),
    )
    fact_recall = SimpleNamespace(
        status="failed",
        facts=(),
        memory_discovery=memory_discovery,
        examined_values=0,
        matching_collection_values=0,
        usable_matching_values=0,
        failures=("memory discovery unavailable",),
        uncertainty=("no discovery receipt was returned",),
    )
    return SimpleNamespace(
        decision=decision,
        decision_date=date(2026, 8, 29),
        memory_id="decision-1",
        decision_preservation=preservation,
        refreshed_sources=(),
        frontier_refresh=None,
        fact_recall=fact_recall,
        week_start_preference="friday",
        user_timezone=None,
        scheduled_draw_dates=(),
        schedule_collection=None,
        numerology_signals=(),
        astrology_observation=None,
        astrology_observation_result=None,
    )


def test_cli_surfaces_failed_fact_recall_receipt(monkeypatch, capsys):
    monkeypatch.setattr(cli, "parse_args", _args)
    monkeypatch.setattr(cli, "run_weekly_decision", lambda *args, **kwargs: _decision_result())

    exit_code = cli.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Kerala fact recall: FAILED" in output
    assert "facts: 0" in output
    assert "examined values: 0" in output
    assert "matching collection values: 0" in output
    assert "usable matching values: 0" in output
    assert "memory discovery: FAILED" in output
    assert "failures: memory discovery unavailable" in output
    assert "uncertainty: no discovery receipt was returned" in output
