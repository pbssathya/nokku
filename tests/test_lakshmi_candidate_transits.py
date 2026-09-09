from datetime import date

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from cossse.memory import Memory

from nokku.lottery.kerala.living import SCHEDULE_DOMAIN, run_weekly_decision


def _schedule_collector(domain_path, source, store=True, requester=None):
    assert domain_path == SCHEDULE_DOMAIN
    assert source == "upcoming"
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
                "source_kind": "official_upcoming_draw_schedule",
                "upcoming_draws": [
                    {
                        "lottery_name": "Karunya",
                        "draw_code": "KR-768",
                        "draw_date": "2026-09-12",
                        "draw_time": "15:00",
                        "draw_venue": "LOTIS fixture",
                    }
                ],
            }
        },
        "execution": {"status": "success"},
    }


def test_living_loop_preserves_factual_transits_at_official_draw_instant(tmp_path):
    memory_path = tmp_path / "living.sqlite"
    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 9, 12),
        week_start_override="sunday",
        refresh=True,
        memory_path=memory_path,
        preferences_path=tmp_path / "preferences.json",
        collector=_schedule_collector,
    )

    observations = result.candidate_transit_observations
    assert observations.status == "success"
    assert observations.failures == ()
    assert observations.uncertainty == ()
    assert len(observations.receipts) == 1

    receipt = observations.receipts[0]
    assert receipt.target_at.isoformat() == "2026-09-12T15:00:00+05:30"
    assert receipt.moon.sign_name == "Virgo"
    assert receipt.moon.degrees_in_sign == pytest.approx(11.15865, abs=0.001)
    assert receipt.jupiter.sign_name == "Cancer"
    assert receipt.jupiter.degrees_in_sign == pytest.approx(21.81443, abs=0.001)

    # Astronomy facts are observational only in this slice.
    assert result.decision.recommendation == "SKIP"

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    stored = recalled["body"]["operational_context"][
        "candidate_draw_transit_observations"
    ]
    assert stored["status"] == "success"
    assert stored["failures"] == []
    assert stored["uncertainty"] == []
    assert len(stored["receipts"]) == 1
    stored_receipt = stored["receipts"][0]
    assert stored_receipt["target_at"] == "2026-09-12T15:00:00+05:30"
    assert stored_receipt["moon"]["sign_name"] == "Virgo"
    assert stored_receipt["jupiter"]["sign_name"] == "Cancer"
