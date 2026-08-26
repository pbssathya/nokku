from nokku.lottery.kerala.astrology import LAKSHMI_ASTROLOGY_CONVENTION


def test_lakshmi_astrology_convention_is_explicit_and_experimental():
    convention = LAKSHMI_ASTROLOGY_CONVENTION

    assert convention.ayanamsa == "lahiri"
    assert convention.dasha_system == "vimshottari"
    assert convention.dasha_year_basis == "julian_365_25"
    assert convention.dasha_days_per_year == 365.25
    assert convention.status == "experimental"
