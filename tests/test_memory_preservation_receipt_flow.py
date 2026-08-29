from datetime import date
import importlib.util
from pathlib import Path
import sys

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

import nokku.lottery.kerala.living as living
from nokku.lottery.kerala.decision import KeralaLotteryFact
from nokku.memory_flow import MemoryPreservationResult


def _failed_preservation() -> MemoryPreservationResult:
    return MemoryPreservationResult(
        status="failed",
        memory_id=None,
        disposition_status="unclaimed",
        feedback_count=0,
        memory_event=None,
        failures=("memory preservation unavailable",),
    )


def _successful_preservation(memory_id: str = "m1") -> MemoryPreservationResult:
    return MemoryPreservationResult(
        status="success",
        memory_id=memory_id,
        disposition_status="claimed",
        feedback_count=1,
        memory_event="preserved",
        stored_at="2026-08-30T00:00:00+00:00",
        sha256="abc123",
    )


def _collector(domain_path, source, store=True, requester=None):
    assert domain_path == living.DOMAIN
    assert source == "75363"
    assert store is False
    assert requester == "nokku"
    return {
        "request": {
            "domain_path": domain_path,
            "source": source,
            "requester": requester,
        },
        "data": {
            "parsed": {
                "draw_date": "29/08/2026",
                "lottery_name": "KARUNYA LOTTERY NO.KR-766th DRAW",
            }
        },
        "execution": {"status": "success"},
    }


def test_frontier_reports_memory_preservation_failure_without_marking_source_refreshed(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        living,
        "preserve_meaning",
        lambda memory, meaning: _failed_preservation(),
        raising=False,
    )

    result = living.refresh_current_frontier_result(
        anchor=date(2026, 8, 29),
        facts=(
            KeralaLotteryFact(
                source="75362",
                draw_date=date(2026, 8, 28),
                lottery_name="SUVARNNA KERALAM SK-67th DRAW",
            ),
        ),
        memory_path=tmp_path / "living.sqlite",
        collector=_collector,
    )

    assert result.status == "failed"
    assert result.refreshed_sources == ()
    assert result.attempted_sources == ("75363",)
    assert result.stop_reason == "memory_preservation_not_successful"
    assert len(result.preservation_attempts) == 1
    assert result.preservation_attempts[0].status == "failed"
    assert result.failures == ("memory preservation unavailable",)


def test_weekly_decision_returns_failed_preservation_receipt_instead_of_asserting(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        living,
        "preserve_meaning",
        lambda memory, meaning: _failed_preservation(),
        raising=False,
    )

    result = living.run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 29),
        refresh=False,
        memory_path=tmp_path / "living.sqlite",
        preferences_path=tmp_path / "preferences.json",
    )

    assert result.decision.recommendation == "SKIP"
    assert result.memory_id is None
    assert result.decision_preservation.status == "failed"
    assert result.decision_preservation.failures == (
        "memory preservation unavailable",
    )


def test_weekly_decision_exposes_successful_preservation_receipt(tmp_path):
    result = living.run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 29),
        refresh=False,
        memory_path=tmp_path / "living.sqlite",
        preferences_path=tmp_path / "preferences.json",
    )

    assert result.decision_preservation.status == "success"
    assert result.decision_preservation.memory_id == result.memory_id
    assert result.memory_id is not None


def test_frontier_payload_preserves_memory_preservation_attempts():
    attempt = _successful_preservation()
    result = living.FrontierRefreshResult(
        status="success",
        refreshed_sources=("75363",),
        attempted_sources=("75363",),
        checkpoint_source="75362",
        checkpoint_draw_date=date(2026, 8, 28),
        stop_reason="anchor_reached",
        preservation_attempts=(attempt,),
    )

    payload = living._frontier_refresh_payload(result)

    assert payload["preservation_attempts"] == [
        {
            "status": "success",
            "memory_id": "m1",
            "disposition_status": "claimed",
            "feedback_count": 1,
            "memory_event": "preserved",
            "stored_at": "2026-08-30T00:00:00+00:00",
            "sha256": "abc123",
            "failures": [],
            "uncertainty": [],
        }
    ]


def test_government_export_carries_frontier_memory_preservation_attempts():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "update_kerala_government.py"
    )
    spec = importlib.util.spec_from_file_location(
        "nokku_test_preservation_update_kerala_government",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    attempt = _successful_preservation()
    result = living.FrontierRefreshResult(
        status="success",
        refreshed_sources=("75363",),
        attempted_sources=("75363",),
        checkpoint_source="75362",
        checkpoint_draw_date=date(2026, 8, 28),
        stop_reason="anchor_reached",
        preservation_attempts=(attempt,),
    )
    receipt = module._receipt_base(
        anchor=date(2026, 8, 29),
        manifest_state="valid",
    )

    assert module._apply_frontier_result(receipt, result) is True
    assert receipt["frontier_refresh"]["preservation_attempts"][0]["status"] == "success"
    assert receipt["frontier_refresh"]["preservation_attempts"][0]["memory_id"] == "m1"
