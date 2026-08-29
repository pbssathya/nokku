from datetime import date
import importlib.util
import json
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
_incremental_export = MODULE._incremental_export
ExportConfig = MODULE.ExportConfig


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


def test_incremental_export_does_not_advance_cutoff_without_new_evidence(tmp_path):
    repository_export = tmp_path / "repository"
    runtime_export = tmp_path / "runtime"
    repository_export.mkdir()
    runtime_export.mkdir()

    config = ExportConfig(
        runtime_export_directory=runtime_export,
        repository_export_directory=repository_export,
        manifest_filename="manifest.json",
        shard_period_format="%Y-%m",
        shard_filename_template="{period}.json",
        frontier_max_new_sources=31,
    )
    manifest = {
        "schema_version": 4,
        "domain_path": "games/chance/lottery/kerala",
        "cutoff_date": "2026-08-29",
        "generated_at": "2026-08-29T13:45:56+00:00",
        "record_count": 1,
        "oldest_source": "75363",
        "oldest_draw_date": "2026-08-29",
        "latest_source": "75363",
        "latest_draw_date": "2026-08-29",
        "shard_period_format": "%Y-%m",
        "shard_filename_template": "{period}.json",
        "shards": [
            {
                "period": "2026-08",
                "file": "2026-08.json",
                "record_count": 1,
                "oldest_source": "75363",
                "oldest_draw_date": "2026-08-29",
                "latest_source": "75363",
                "latest_draw_date": "2026-08-29",
            }
        ],
    }
    (repository_export / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    final_manifest, changed_files, added, updated, manifest_changed = (
        _incremental_export(
            config=config,
            manifest=manifest,
            anchor=date(2026, 8, 30),
            new_records=[],
        )
    )

    assert final_manifest["cutoff_date"] == "2026-08-29"
    assert changed_files == []
    assert added == 0
    assert updated == 0
    assert manifest_changed is False
