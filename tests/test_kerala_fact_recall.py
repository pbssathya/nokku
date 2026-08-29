from datetime import date

from nokku.lottery.kerala.fact_recall import interpret_kerala_fact_values
from nokku.memory_flow import MemoryDiscoveryResult


def _discovery(*values, status="success", failures=(), uncertainty=()):
    return MemoryDiscoveryResult(
        status=status,
        values=tuple(values),
        discovered_receipt_count=len(values),
        attempted_memory_ids=tuple(f"memory-{index}" for index in range(len(values))),
        discovery_disposition_status="claimed",
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )


def _kerala_value(
    source="75363",
    *,
    draw_date="29/08/2026",
    lottery_name="Karunya KR-766",
    execution_status="success",
):
    return {
        "body": {
            "experience": "capability_attempt",
            "capability": "collect",
            "outcome": {
                "request": {
                    "domain_path": "games/chance/lottery/kerala",
                    "source": source,
                },
                "execution": {"status": execution_status},
                "data": {
                    "parsed": {
                        "draw_date": draw_date,
                        "lottery_name": lottery_name,
                    }
                },
            },
        }
    }


def test_fact_recall_filters_unrelated_values_without_treating_them_as_failures():
    unrelated = {
        "body": {
            "experience": "decision",
            "application": "nokku",
        }
    }
    result = interpret_kerala_fact_values(
        _discovery(unrelated, _kerala_value())
    )

    assert result.status == "success"
    assert result.examined_values == 2
    assert result.matching_collection_values == 1
    assert result.usable_matching_values == 1
    assert result.facts == (
        result.facts[0],
    )
    assert result.facts[0].source == "75363"
    assert result.facts[0].draw_date == date(2026, 8, 29)
    assert result.failures == ()
    assert result.uncertainty == ()


def test_fact_recall_surfaces_matching_malformed_evidence_instead_of_dropping_it():
    result = interpret_kerala_fact_values(
        _discovery(
            _kerala_value(source="75362", draw_date="not-a-date"),
            _kerala_value(source="75363"),
        )
    )

    assert result.status == "partial"
    assert [fact.source for fact in result.facts] == ["75363"]
    assert result.matching_collection_values == 2
    assert result.usable_matching_values == 1
    assert result.failures == ()
    assert result.uncertainty == (
        "Kerala collection evidence 75362 has no usable draw date",
    )


def test_fact_recall_propagates_memory_handoff_failure():
    result = interpret_kerala_fact_values(
        _discovery(
            status="failed",
            failures=("memory discovery was not singly claimed",),
        )
    )

    assert result.status == "failed"
    assert result.facts == ()
    assert result.failures == ("memory discovery was not singly claimed",)
