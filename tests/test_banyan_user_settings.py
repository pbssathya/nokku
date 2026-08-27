from banyan.user_settings import (
    UserBirthProfile as BanyanUserBirthProfile,
    UserPreferences as BanyanUserPreferences,
)
from nokku.preferences import UserBirthProfile, UserPreferences


def test_nokku_user_setting_types_are_banyan_types():
    """Nokku must consume the shared Banyan user-setting model, not duplicate it."""
    assert UserBirthProfile is BanyanUserBirthProfile
    assert UserPreferences is BanyanUserPreferences
