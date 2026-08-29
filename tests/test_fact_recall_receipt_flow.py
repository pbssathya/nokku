from datetime import date

import pytest

pytest.importorskip("collector")
pytest.importorskip("cossse")

from cossse.memory import Memory

from nokku.lottery.kerala.living import run_weekly_decision


def test_living_decision_exposes_and_preserves_fact_recall_receipt(tmp_path):
    memory_path = tmp_path / "living.sqlite"

    result = run_weekly_decision(
        "Should I buy a Kerala lottery this week?",
        anchor=date(2026, 8, 29),
        refresh=False,
        memory_path=memory_path,
        preferences_path=tmp_path / "preferences.json",
    )

    assert result.fact_recall.status == "success"
    assert result.fact_recall.facts == ()
    assert result.fact_recall.examined_values == 0
    assert result.fact_recall.matching_collection_values == 0
    assert result.fact_recall.usable_matching_values == 0
    assert result.fact_recall.failures == ()
    assert result.fact_recall.uncertainty == ()

    with Memory(memory_path) as memory:
        recalled = memory.recall(result.memory_id)

    receipt = recalled["body"]["operational_context"]["kerala_fact_recall"]
    assert receipt["status"] == "success"
    assert receipt["fact_count"] == 0
    assert receipt["examined_values"] == 0
    assert receipt["matching_collection_values"] == 0
    assert receipt["usable_matching_values"] == 0
    assert receipt["memory_discovery"]["status"] == "success"
    assert receipt["memory_discovery"]["discovered_receipt_count"] == 0
    assert receipt["failures"] == []
    assert receipt["uncertainty"] == []
