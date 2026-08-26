from datetime import date

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from cossse.memory import Memory

from nokku.lottery.kerala.living import SCHEDULE_DOMAIN, run_weekly_decision
from nokku.preferences import UserBirthProfile, UserPreferences, save_user_preferences


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
                    {"draw_date": "2026-08-27", "draw_code": "KN-638"},
                    {"draw_date": "2026-08-28", "draw_code": "SK-67"},
                    {"draw_date": "2026-08-29", "draw_code": "KR-766"},
                ],
            }
        },
        "execution": {"status": "success"},
    }


def _save_lakshmi_profile(preferences_path):
    save_user_preferences(
        UserPreferences(
            timezone="Asia/Kolkata",
            birth=UserBirthProfile(
                date="1969-08-12",
                time="05:23",
                location="Kannankulangara, North Paravur, Kerala",
            ),
        ),
        preferences_path,
    )


def test_living_loop_never_selects_unlisted_26_august(tmp_path):
    preferences_path = tmp_path / "preferences.json"
    _save_lakshmi_profile(preferences_path)

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 26),
        refresh=True,
        memory_path=tmp_path / "living.sqlite",
        preferences_path=preferences_path,
        collector=_schedule_collector,
    )

    assert result.decision.recommendation == "SKIP"
    assert result.scheduled_draw_dates == (
        date(2026, 8, 27),
        date(2026, 8, 28),
        date(2026, 8, 29),
    )
    assert result.decision.preferred_date == date(2026, 8, 27)
    assert result.decision.backup_date is None
    assert date(2026, 8, 26) not in {
        result.decision.preferred_date,
        result.decision.backup_date,
    }
    assert [signal.target_date for signal in result.numerology_signals] == [
        date(2026, 8, 27)
    ]
    signal = result.numerology_signals[0]
    assert signal.draw_number == "638"
    assert signal.draw_reduction == 8

    with Memory(tmp_path / "living.sqlite") as memory:
        recalled = memory.recall(result.memory_id)

    assert recalled["body"]["operational_context"]["official_upcoming_draw_dates"] == [
        "2026-08-27",
        "2026-08-28",
        "2026-08-29",
    ]
    preserved = recalled["body"]["signals"]["numerology"][0]
    assert preserved["draw_number"] == "638"
    assert preserved["draw_reduction"] == 8


def test_sunday_week_uses_recovered_numerology_to_prefer_28_august(tmp_path):
    preferences_path = tmp_path / "preferences.json"
    _save_lakshmi_profile(preferences_path)

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 26),
        week_start_override="sunday",
        refresh=True,
        memory_path=tmp_path / "living.sqlite",
        preferences_path=preferences_path,
        collector=_schedule_collector,
    )

    assert result.decision.week_start == date(2026, 8, 23)
    assert result.decision.week_end == date(2026, 8, 29)
    assert result.decision.recommendation == "SKIP"
    assert result.decision.preferred_date == date(2026, 8, 28)
    assert result.decision.backup_date == date(2026, 8, 29)

    by_date = {signal.target_date: signal for signal in result.numerology_signals}
    assert set(by_date) == {
        date(2026, 8, 27),
        date(2026, 8, 28),
        date(2026, 8, 29),
    }
    assert by_date[date(2026, 8, 27)].personal_day == 2
    assert by_date[date(2026, 8, 28)].personal_day == 3
    assert by_date[date(2026, 8, 28)].personal_day_in_369_family is True
    assert by_date[date(2026, 8, 28)].personal_day_matches_birth_number is True
    assert by_date[date(2026, 8, 28)].personal_day_matches_personal_year is True
    assert by_date[date(2026, 8, 28)].draw_number == "67"
    assert by_date[date(2026, 8, 28)].draw_reduction == 4
    assert by_date[date(2026, 8, 29)].personal_day == 4
    assert any(
        "experimental Lakshmi numerology ordering is active" in item
        for item in result.decision.evidence_summary
    )
