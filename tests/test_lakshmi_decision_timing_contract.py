from datetime import date

from nokku.lottery.kerala.decision import (
    KeralaLotteryDecision,
    KeralaLotteryDecisionTiming,
    KeralaLotteryTimeWindow,
)


def test_lakshmi_timing_contract_serializes_distinct_time_layers():
    timing = KeralaLotteryDecisionTiming(
        official_draw_time=KeralaLotteryTimeWindow(
            value="15:00",
            timezone="Asia/Kolkata",
            basis="official draw schedule",
            status="government_verified",
        ),
        official_sale_cutoff=KeralaLotteryTimeWindow(
            value="NOT VERIFIED",
            timezone="Asia/Kolkata",
            basis="official cutoff not yet verified",
            status="not_verified",
        ),
        operational_purchase_window=KeralaLotteryTimeWindow(
            value="before verified sale cutoff",
            timezone="Asia/Kolkata",
            basis="operational safety margin requires a verified cutoff",
            status="operational_inferred",
        ),
        primary_preferred_window=KeralaLotteryTimeWindow(
            value="10:30-11:15",
            timezone="Asia/Kolkata",
            basis="example symbolic window supplied by the caller",
            status="symbolic_derived",
        ),
        backup_window=KeralaLotteryTimeWindow(
            value="12:00-12:30",
            timezone="Asia/Kolkata",
            basis="example symbolic backup supplied by the caller",
            status="symbolic_derived",
        ),
        avoid_windows=(
            KeralaLotteryTimeWindow(
                value="13:30-14:00",
                timezone="Asia/Kolkata",
                basis="example symbolic caution supplied by the caller",
                status="symbolic_derived",
            ),
        ),
        uncertainty=("official sale cutoff remains unverified",),
    )
    decision = KeralaLotteryDecision(
        recommendation="BUY",
        week_start=date(2026, 9, 6),
        week_end=date(2026, 9, 12),
        preferred_date=date(2026, 9, 12),
        backup_date=None,
        preferred_time="legacy compatibility summary",
        evidence_summary=("test evidence",),
        uncertainty="test uncertainty",
        timing=timing,
    )

    payload = decision.to_dict()

    assert payload["preferred_time"] == "legacy compatibility summary"
    assert payload["timing"]["official_draw_time"] == {
        "value": "15:00",
        "timezone": "Asia/Kolkata",
        "basis": "official draw schedule",
        "status": "government_verified",
    }
    assert payload["timing"]["official_sale_cutoff"]["status"] == "not_verified"
    assert payload["timing"]["operational_purchase_window"]["status"] == "operational_inferred"
    assert payload["timing"]["primary_preferred_window"]["status"] == "symbolic_derived"
    assert payload["timing"]["backup_window"]["value"] == "12:00-12:30"
    assert payload["timing"]["avoid_windows"][0]["value"] == "13:30-14:00"
    assert payload["timing"]["uncertainty"] == (
        "official sale cutoff remains unverified",
    )


def test_existing_decision_contract_can_remain_unmigrated_temporarily():
    decision = KeralaLotteryDecision(
        recommendation="SKIP",
        week_start=date(2026, 9, 6),
        week_end=date(2026, 9, 12),
        preferred_date=None,
        backup_date=None,
        preferred_time="before the official sales cutoff; no predictive time advantage inferred",
        evidence_summary=("neutral evidence",),
        uncertainty="random outcome",
    )

    payload = decision.to_dict()

    assert decision.timing is None
    assert payload["timing"] is None
    assert payload["preferred_time"] == (
        "before the official sales cutoff; no predictive time advantage inferred"
    )
