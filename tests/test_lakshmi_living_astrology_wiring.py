from datetime import date

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from banyan.user_settings import UserBirthProfile, UserPreferences
from cossse.memory import Memory

from nokku.lottery.kerala.living import SCHEDULE_DOMAIN, run_weekly_decision
from nokku.preferences import save_user_preferences


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


def test_living_loop_derives_and_preserves_candidate_astrology_without_policy_effect(tmp_path):
    memory_path = tmp_path / "living.sqlite"
    preferences_path = tmp_path / "preferences.json"
    save_user_preferences(
        UserPreferences(
            timezone="Asia/Kolkata",
            birth=UserBirthProfile(
                date="2000-01-01",
                time="00:00",
                location="Test Location",
                timezone="Asia/Kolkata",
            ),
        ),
        preferences_path,
    )

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 9, 12),
        week_start_override="sunday",
        refresh=True,
        memory_path=memory_path,
        preferences_path=preferences_path,
        collector=_schedule_collector,
    )

    assert result.natal_astrology_context.status == "success"
    assert result.natal_astrology_context.moon is not None
    assert result.natal_astrology_context.jupiter is not None

    assert len(result.candidate_astrology_interpretations) == 1
    interpretation = result.candidate_astrology_interpretations[0]
    assert interpretation.status == "success"
    assert interpretation.method == "lakshmi_moon_natal_jupiter_conjunction_v1"
    assert interpretation.target_at.isoformat() == "2026-09-12T15:00:00+05:30"

    # This slice exposes interpretation evidence only; policy is unchanged.
    assert result.decision.recommendation == "SKIP"

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    signals = recalled["body"]["signals"]
    assert signals["natal_astrology_context"]["status"] == "success"
    assert signals["natal_astrology_context"]["moon"] is not None
    assert signals["natal_astrology_context"]["jupiter"] is not None
    assert len(signals["candidate_astrology"]) == 1
    stored = signals["candidate_astrology"][0]
    assert stored["status"] == "success"
    assert stored["method"] == "lakshmi_moon_natal_jupiter_conjunction_v1"
    assert stored["target_at"] == "2026-09-12T15:00:00+05:30"
