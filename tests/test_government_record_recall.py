from datetime import date

from nokku.lottery.kerala.government_record_recall import (
    interpret_government_record_values,
)
from nokku.memory_flow import MemoryDiscoveryResult


def _memory_result(*values, status="success", failures=(), uncertainty=()):
    return MemoryDiscoveryResult(
        status=status,
        values=tuple(values),
        discovered_receipt_count=len(values),
        attempted_memory_ids=tuple(f"m{i}" for i in range(len(values))),
        discovery_disposition_status="claimed",
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )


def _collect_value(
    *,
    source="75363",
    draw_date="29/08/2026",
    lottery_name="Karunya KR-766",
    status="success",
    parsed_extra=None,
):
    parsed = {
        "draw_date": draw_date,
        "lottery_name": lottery_name,
        "prize_tiers": [{"label": "1st Prize", "amount": "100"}],
    }
    if parsed_extra:
        parsed.update(parsed_extra)
    return {
        "body": {
            "experience": "capability_attempt",
            "capability": "collect",
            "outcome": {
                "request": {
                    "domain_path": "games/chance/lottery/kerala",
                    "source": source,
                },
                "execution": {"status": status},
                "data": {"parsed": parsed},
            },
        }
    }


def test_government_record_recall_preserves_full_parsed_payload():
    discovery = _memory_result(_collect_value())

    result = interpret_government_record_values(
        discovery,
        anchor=date(2026, 8, 29),
    )

    assert result.status == "success"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["source"] == "75363"
    assert record["parsed"]["prize_tiers"] == [
        {"label": "1st Prize", "amount": "100"}
    ]
    assert result.matching_collection_values == 1
    assert result.usable_matching_values == 1
    assert result.failures == ()
    assert result.uncertainty == ()


def test_government_record_recall_reports_matching_unusable_evidence():
    discovery = _memory_result(
        _collect_value(source="75363", draw_date="Unknown"),
        _collect_value(source="75364", status="failed"),
    )

    result = interpret_government_record_values(
        discovery,
        anchor=date(2026, 8, 29),
    )

    assert result.status == "partial"
    assert result.records == ()
    assert result.matching_collection_values == 2
    assert result.usable_matching_values == 0
    assert any("75363 has no usable draw date" in item for item in result.uncertainty)
    assert any("75364 has unusable execution status: failed" in item for item in result.uncertainty)


def test_government_record_recall_reports_normal_filters_separately():
    discovery = _memory_result(
        _collect_value(source="75362", draw_date="28/08/2026"),
        _collect_value(source="75363", draw_date="29/08/2026"),
        _collect_value(source="75364", draw_date="30/08/2026"),
    )

    result = interpret_government_record_values(
        discovery,
        anchor=date(2026, 8, 29),
        min_numeric_source_exclusive=75362,
    )

    assert result.status == "success"
    assert [record["source"] for record in result.records] == ["75363"]
    assert result.filtered_by_checkpoint == 1
    assert result.filtered_after_anchor == 1
    assert result.failures == ()
    assert result.uncertainty == ()


def test_checkpoint_scope_excludes_old_failed_attempt_before_interpretation():
    discovery = _memory_result(
        _collect_value(source="75362", status="failed"),
        _collect_value(source="75363", draw_date="29/08/2026"),
    )

    result = interpret_government_record_values(
        discovery,
        anchor=date(2026, 8, 29),
        min_numeric_source_exclusive=75362,
    )

    assert result.status == "success"
    assert [record["source"] for record in result.records] == ["75363"]
    assert result.filtered_by_checkpoint == 1
    assert result.usable_matching_values == 1
    assert result.failures == ()
    assert result.uncertainty == ()
