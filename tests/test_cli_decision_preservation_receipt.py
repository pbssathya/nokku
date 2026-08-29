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
        status="failed",
        memory_id=None,
        disposition_status="unclaimed",
        feedback_count=0,
        memory_event=None,
        failures=("memory preservation unavailable",),
        uncertainty=("no preservation receipt was returned",),
    )
    return SimpleNamespace(
        decision=decision,
        decision_date=date(2026, 8, 29),
        memory_id=None,
        decision_preservation=preservation,
        refreshed_sources=(),
        week_start_preference="friday",
        user_timezone=None,
        scheduled_draw_dates=(),
        numerology_signals=(),
        astrology_observation=None,
        astrology_observation_result=None,
    )


def test_cli_surfaces_failed_decision_preservation_receipt(monkeypatch, capsys):
    monkeypatch.setattr(cli, "parse_args", _args)
    monkeypatch.setattr(cli, "run_weekly_decision", lambda *args, **kwargs: _decision_result())

    exit_code = cli.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "decision memory preservation: FAILED" in output
    assert "memory id: NONE" in output
    assert "failures: memory preservation unavailable" in output
    assert "uncertainty: no preservation receipt was returned" in output
