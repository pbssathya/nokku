from datetime import date
import importlib.util
from pathlib import Path
import sys

from nokku.lottery.kerala.government_record_recall import GovernmentRecordRecallResult
from nokku.memory_flow import MemoryDiscoveryResult


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "update_kerala_government.py"
)
SPEC = importlib.util.spec_from_file_location(
    "nokku_test_update_kerala_government_record_recall",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

_apply_government_record_recall = MODULE._apply_government_record_recall
_receipt_base = MODULE._receipt_base


def _memory_result(*, status="success", failures=(), uncertainty=()):
    return MemoryDiscoveryResult(
        status=status,
        values=(),
        discovered_receipt_count=0,
        attempted_memory_ids=(),
        discovery_disposition_status="claimed",
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )


def _record_result(*, status="success", failures=(), uncertainty=()):
    return GovernmentRecordRecallResult(
        status=status,
        records=(),
        memory_discovery=_memory_result(
            status=("success" if status == "success" else "partial"),
            failures=failures,
            uncertainty=uncertainty,
        ),
        examined_values=0,
        matching_collection_values=0,
        usable_matching_values=0,
        filtered_by_checkpoint=0,
        filtered_after_anchor=0,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )


def test_export_accepts_successful_government_record_recall():
    receipt = _receipt_base(
        anchor=date(2026, 8, 30),
        manifest_state="valid",
    )
    result = _record_result()

    assert _apply_government_record_recall(receipt, result) is True
    assert receipt["status"] == "success"
    assert len(receipt["government_record_recall_attempts"]) == 1
    attempt = receipt["government_record_recall_attempts"][0]
    assert attempt["status"] == "success"
    assert attempt["record_count"] == 0
    assert attempt["memory_discovery"]["status"] == "success"


def test_export_surfaces_partial_government_record_recall_for_upper_decision():
    receipt = _receipt_base(
        anchor=date(2026, 8, 30),
        manifest_state="valid",
    )
    result = _record_result(
        status="partial",
        uncertainty=("Government collection evidence 75364 has no usable draw date",),
    )

    assert _apply_government_record_recall(receipt, result) is False
    assert receipt["status"] == "needs_decision"
    assert receipt["uncertainty"] == [
        "Government collection evidence 75364 has no usable draw date"
    ]
    assert receipt["government_record_recall_attempts"][0]["status"] == "partial"


def test_export_preserves_multiple_government_record_recall_attempts():
    receipt = _receipt_base(
        anchor=date(2026, 8, 30),
        manifest_state="valid",
    )

    assert _apply_government_record_recall(receipt, _record_result()) is True
    assert _apply_government_record_recall(receipt, _record_result()) is True

    assert len(receipt["government_record_recall_attempts"]) == 2


def test_exporter_no_longer_uses_silent_memory_discovery_path():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "_discover_values" not in source
    assert "recall_government_records_result" in source
