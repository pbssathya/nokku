from datetime import date

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from nokku.lottery.kerala.decision import KeralaLotteryFact
from nokku.lottery.kerala.living import DOMAIN, refresh_current_frontier_result


def test_frontier_receipt_distinguishes_already_current_without_collecting(tmp_path):
    called = False

    def collector(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("collector must not run when checkpoint is already current")

    result = refresh_current_frontier_result(
        anchor=date(2026, 8, 29),
        facts=(
            KeralaLotteryFact(
                source="75363",
                draw_date=date(2026, 8, 29),
                lottery_name="KARUNYA LOTTERY NO.KR-766th DRAW",
            ),
        ),
        memory_path=tmp_path / "living.sqlite",
        collector=collector,
    )

    assert called is False
    assert result.status == "current"
    assert result.refreshed_sources == ()
    assert result.attempted_sources == ()
    assert result.stop_reason == "checkpoint_current_through_anchor"
    assert result.failures == ()


def test_frontier_receipt_reports_collector_failure_instead_of_empty_success(tmp_path):
    def collector(domain_path, source, store=True, requester=None):
        assert domain_path == DOMAIN
        assert source == "75363"
        assert store is False
        assert requester == "nokku"
        return {
            "request": {
                "domain_path": domain_path,
                "source": source,
                "requester": requester,
            },
            "data": {"parsed": {}},
            "execution": {"status": "failed"},
        }

    result = refresh_current_frontier_result(
        anchor=date(2026, 8, 29),
        facts=(
            KeralaLotteryFact(
                source="75362",
                draw_date=date(2026, 8, 28),
                lottery_name="SUVARNNA KERALAM SK-67th DRAW",
            ),
        ),
        memory_path=tmp_path / "living.sqlite",
        collector=collector,
    )

    assert result.status == "failed"
    assert result.refreshed_sources == ()
    assert result.attempted_sources == ("75363",)
    assert result.stop_reason == "collector_execution_not_usable"
    assert result.failures == ("source 75363 collector execution status: failed",)


def test_frontier_receipt_reports_success_and_preserved_source(tmp_path):
    def collector(domain_path, source, store=True, requester=None):
        assert domain_path == DOMAIN
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

    result = refresh_current_frontier_result(
        anchor=date(2026, 8, 29),
        facts=(
            KeralaLotteryFact(
                source="75362",
                draw_date=date(2026, 8, 28),
                lottery_name="SUVARNNA KERALAM SK-67th DRAW",
            ),
        ),
        memory_path=tmp_path / "living.sqlite",
        collector=collector,
    )

    assert result.status == "success"
    assert result.refreshed_sources == ("75363",)
    assert result.attempted_sources == ("75363",)
    assert result.stop_reason == "anchor_reached"
    assert result.failures == ()
    assert result.uncertainty == ()
