from datetime import timedelta

import pytest

from nokku.__main__ import parse_aware_datetime


def test_cli_astrology_target_requires_explicit_timezone():
    parsed = parse_aware_datetime("2026-08-28T12:00:00+05:30")

    assert parsed.isoformat() == "2026-08-28T12:00:00+05:30"
    assert parsed.utcoffset() == timedelta(hours=5, minutes=30)

    with pytest.raises(ValueError, match="timezone-aware"):
        parse_aware_datetime("2026-08-28T12:00:00")
