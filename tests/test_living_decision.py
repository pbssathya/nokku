from datetime import date, datetime, timezone

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from cossse.memory import Memory

from nokku.lottery.kerala.living import (
    MissingUserTimezoneError,
    kerala_today,
    local_today,
    run_weekly_decision,
)
from nokku.preferences import (
    UserBirthProfile,
    UserPreferences,
    save_user_preferences,
)


def test_kerala_today_uses_ist_not_codespace_utc():
    utc_late_evening = datetime(2026, 8, 23, 20, 0, tzinfo=timezone.utc)

    assert kerala_today(utc_late_evening) == date(2026, 8, 24)


def test_local_today_uses_user_timezone_not_domain_timezone():
    utc_late_evening = datetime(2026, 8, 23, 20, 0, tzinfo=timezone.utc)

    assert local_today("Asia/Kolkata", utc_late_evening) == date(2026, 8, 24)
    assert local_today("America/New_York", utc_late_evening) == date(2026, 8, 23)


def test_undated_request_requires_user_timezone(tmp_path):
    with pytest.raises(MissingUserTimezoneError):
        run_weekly_decision(
            "Should I buy a Kerala lottery this week?",
            refresh=False,
            memory_path=tmp_path / "living.sqlite",
            preferences_path=tmp_path / "preferences.json",
        )


def test_saved_user_timezone_resolves_undated_decision_date(tmp_path):
    memory_path = tmp_path / "living.sqlite"
    preferences_path = tmp_path / "preferences.json"
    save_user_preferences(UserPreferences(timezone="Asia/Kolkata"), preferences_path)

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        refresh=False,
        memory_path=memory_path,
        preferences_path=preferences_path,
        now=datetime(2026, 8, 23, 20, 0, tzinfo=timezone.utc),
    )

    assert result.decision_date == date(2026, 8, 24)
    assert result.user_timezone == "Asia/Kolkata"


def test_temporary_timezone_override_can_be_remembered(tmp_path):
    preferences_path = tmp_path / "preferences.json"

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        timezone_override="Europe/London",
        remember_timezone=True,
        refresh=False,
        memory_path=tmp_path / "living.sqlite",
        preferences_path=preferences_path,
        now=datetime(2026, 8, 23, 20, 0, tzinfo=timezone.utc),
    )

    assert result.decision_date == date(2026, 8, 23)
    assert result.user_timezone == "Europe/London"


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
    assert result.numerology_signals == ()
    assert result.astrology_observation is None

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    assert recalled["body"]["experience"] == "decision"
    assert recalled["body"]["application"] == "nokku"
    assert recalled["body"]["decision_type"] == "weekly_participation"
    assert recalled["body"]["decision"]["recommendation"] == "SKIP"
    assert recalled["body"]["signals"]["numerology"] == []
    assert recalled["body"]["signals"]["astrology"] is None


def test_living_loop_observes_saved_profile_numerology_without_changing_policy(tmp_path):
    memory_path = tmp_path / "living.sqlite"
    preferences_path = tmp_path / "preferences.json"
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

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 24),
        refresh=False,
        memory_path=memory_path,
        preferences_path=preferences_path,
    )

    assert result.decision.recommendation == "SKIP"
    by_date = {signal.target_date: signal for signal in result.numerology_signals}
    assert by_date[date(2026, 8, 24)].personal_day == 8
    assert by_date[date(2026, 8, 25)].personal_day == 9
    assert by_date[date(2026, 8, 25)].birth_number == 3
    assert by_date[date(2026, 8, 25)].life_path == 9
    assert by_date[date(2026, 8, 25)].personal_year == 3
    assert by_date[date(2026, 8, 25)].personal_month_compound == 11
    assert by_date[date(2026, 8, 25)].personal_month == 2

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    preserved = {
        item["target_date"]: item
        for item in recalled["body"]["signals"]["numerology"]
    }
    assert preserved["2026-08-25"]["personal_day"] == 9
    assert preserved["2026-08-25"]["personal_day_in_369_family"] is True


def test_living_loop_preserves_explicit_astrology_observation_without_changing_policy(
    tmp_path,
):
    memory_path = tmp_path / "living.sqlite"
    preferences_path = tmp_path / "preferences.json"
    save_user_preferences(
        UserPreferences(
            timezone="Europe/London",
            birth=UserBirthProfile(
                date="1969-08-12",
                time="05:23",
                location="Kannankulangara, North Paravur, Kerala",
                timezone="Asia/Kolkata",
            ),
        ),
        preferences_path,
    )

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 24),
        refresh=False,
        memory_path=memory_path,
        preferences_path=preferences_path,
        astrology_target_at=datetime(2026, 8, 28, 6, 30, tzinfo=timezone.utc),
    )

    assert result.decision.recommendation == "SKIP"
    assert result.astrology_observation is not None
    assert result.astrology_observation.mahadasha == "Moon"
    assert result.astrology_observation.antardasha == "Moon"
    assert result.astrology_observation.status == "experimental"

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    preserved = recalled["body"]["signals"]["astrology"]
    assert preserved["mahadasha"] == "Moon"
    assert preserved["antardasha"] == "Moon"
    assert preserved["status"] == "experimental"


def test_living_loop_does_not_substitute_current_timezone_for_birth_timezone(tmp_path):
    memory_path = tmp_path / "living.sqlite"
    preferences_path = tmp_path / "preferences.json"
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

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 24),
        refresh=False,
        memory_path=memory_path,
        preferences_path=preferences_path,
        astrology_target_at=datetime(2026, 8, 28, 6, 30, tzinfo=timezone.utc),
    )

    assert result.decision.recommendation == "SKIP"
    assert result.astrology_observation is None

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    assert recalled["body"]["signals"]["astrology"] is None


def test_living_loop_rejects_timezone_naive_astrology_target(tmp_path):
    preferences_path = tmp_path / "preferences.json"
    save_user_preferences(
        UserPreferences(
            birth=UserBirthProfile(
                date="1969-08-12",
                time="05:23",
                location="Kannankulangara, North Paravur, Kerala",
                timezone="Asia/Kolkata",
            ),
        ),
        preferences_path,
    )

    with pytest.raises(ValueError, match="astrology target instant must be timezone-aware"):
        run_weekly_decision(
            "Should I buy a Kerala lottery this week?",
            anchor=date(2026, 8, 24),
            refresh=False,
            memory_path=tmp_path / "living.sqlite",
            preferences_path=preferences_path,
            astrology_target_at=datetime(2026, 8, 28, 12, 0),
        )


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
