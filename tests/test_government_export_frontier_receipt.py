from datetime import date
import importlib.util
from pathlib import Path
import sys

from nokku.lottery.kerala.living import FrontierRefreshResult


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "update_kerala_government.py"
)
SPEC = importlib.util.spec_from_file_location(
    "nokku_test_update_kerala_government",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

_apply_frontier_result = MODULE._apply_frontier_result
_receipt_base = MODULE._receipt_base


def test_export_accepts_current_frontier_receipt():
    receipt = _receipt_base(
        anchor=date(2026, 8, 29),
        manifest_state="valid",
    )
    result = FrontierRefreshResult(
        status="current",
        refreshed_sources=(),
        attempted_sources=(),
        checkpoint_source="75363",
        checkpoint_draw_date=date(2026, 8, 29),
        stop_reason="checkpoint_current_through_anchor",
    )

    assert _apply_frontier_result(receipt, result) is True
    assert receipt["status"] == "success"
    assert receipt["collector_sources_added"] == []
    assert receipt["frontier_refresh"]["status"] == "current"
    assert receipt["frontier_refresh"]["stop_reason"] == (
        "checkpoint_current_through_anchor"
    )


def test_export_surfaces_failed_frontier_for_upper_decision():
    receipt = _receipt_base(
        anchor=date(2026, 8, 29),
        manifest_state="valid",
    )
    result = FrontierRefreshResult(
        status="failed",
        refreshed_sources=(),
        attempted_sources=("75364",),
        checkpoint_source="75363",
        checkpoint_draw_date=date(2026, 8, 28),
        stop_reason="collector_execution_not_usable",
        failures=("source 75364 collector execution status: failed",),
    )

    assert _apply_frontier_result(receipt, result) is False
    assert receipt["status"] == "needs_decision"
    assert receipt["collector_sources_added"] == []
    assert receipt["failures"] == [
        "source 75364 collector execution status: failed"
    ]


def test_export_preserves_partial_frontier_energy_without_silencing_it():
    receipt = _receipt_base(
        anchor=date(2026, 8, 29),
        manifest_state="valid",
    )
    result = FrontierRefreshResult(
        status="partial",
        refreshed_sources=("75364",),
        attempted_sources=("75364",),
        checkpoint_source="75363",
        checkpoint_draw_date=date(2026, 8, 28),
        stop_reason="max_new_sources_reached",
        uncertainty=("frontier limit reached before anchor",),
    )

    assert _apply_frontier_result(receipt, result) is False
    assert receipt["status"] == "needs_decision"
    assert receipt["collector_sources_added"] == ["75364"]
    assert receipt["uncertainty"] == [
        "frontier limit reached before anchor"
    ]
