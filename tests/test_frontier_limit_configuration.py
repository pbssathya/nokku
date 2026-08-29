from datetime import date, timedelta

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from nokku.lottery.kerala.decision import KeralaLotteryFact
from nokku.lottery.kerala.living import DOMAIN, refresh_current_frontier_result


CHECKPOINT_SOURCE = 75350
CHECKPOINT_DATE = date(2026, 8, 20)


def _collector(domain_path, source, store=True, requester=None):
    assert domain_path == DOMAIN
    assert store is False
    assert requester == "nokku"

    offset = int(source) - CHECKPOINT_SOURCE
    draw_date = CHECKPOINT_DATE + timedelta(days=offset)
    return {
        "request": {
            "domain_path": domain_path,
            "source": source,
            "requester": requester,
        },
        "data": {
            "parsed": {
                "draw_date": draw_date.strftime("%d/%m/%Y"),
                "lottery_name": f"TEST LOTTERY SOURCE {source}",
            }
        },
        "execution": {"status": "success"},
    }


def _facts():
    return (
        KeralaLotteryFact(
            source=str(CHECKPOINT_SOURCE),
            draw_date=CHECKPOINT_DATE,
            lottery_name="TEST CHECKPOINT",
        ),
    )


def test_frontier_without_explicit_limit_can_cross_old_seven_source_boundary(tmp_path):
    result = refresh_current_frontier_result(
        anchor=date(2026, 8, 29),
        facts=_facts(),
        memory_path=tmp_path / "living.sqlite",
        collector=_collector,
    )

    assert result.status == "success"
    assert result.stop_reason == "anchor_reached"
    assert len(result.refreshed_sources) == 9
    assert result.refreshed_sources[-1] == "75359"


def test_frontier_honors_explicit_upper_layer_limit(tmp_path):
    result = refresh_current_frontier_result(
        anchor=date(2026, 8, 29),
        facts=_facts(),
        memory_path=tmp_path / "living.sqlite",
        max_new_sources=2,
        collector=_collector,
    )

    assert result.status == "partial"
    assert result.refreshed_sources == ("75351", "75352")
    assert result.attempted_sources == ("75351", "75352")
    assert result.stop_reason == "max_new_sources_reached"
    assert result.uncertainty == ("frontier limit reached before anchor",)
