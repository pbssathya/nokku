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


def test_living_decision_carries_verified_draw_time_without_inventing_other_windows(
    tmp_path,
):
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

    assert result.decision.preferred_date == date(2026, 9, 12)
    assert result.schedule_collection is not None
    assert result.schedule_collection.draw_times == {date(2026, 9, 12): "15:00"}

    timing = result.decision.timing
    assert timing is not None
    assert timing.official_draw_time is not None
    assert timing.official_draw_time.value == "15:00"
    assert timing.official_draw_time.timezone == "Asia/Kolkata"
    assert timing.official_draw_time.status == "government_verified"

    assert timing.official_sale_cutoff is not None
    assert timing.official_sale_cutoff.value == "NOT VERIFIED"
    assert timing.official_sale_cutoff.status == "not_verified"
    assert timing.operational_purchase_window is None
    assert timing.primary_preferred_window is None
    assert timing.backup_window is None
    assert timing.avoid_windows == ()
    assert "official sale/purchase cutoff not verified" in timing.uncertainty
    assert (
        "symbolic preferred/backup/avoid windows not yet supplied by the symbolic layer"
        in timing.uncertainty
    )

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    stored_schedule = recalled["body"]["operational_context"][
        "official_upcoming_draw_schedule_collection"
    ]
    assert stored_schedule["draw_times"] == {"2026-09-12": "15:00"}

    stored_timing = recalled["body"]["decision"]["timing"]
    assert stored_timing["official_draw_time"]["value"] == "15:00"
    assert stored_timing["official_draw_time"]["status"] == "government_verified"
    assert stored_timing["official_sale_cutoff"]["status"] == "not_verified"
