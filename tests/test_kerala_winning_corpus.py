from __future__ import annotations

import json
from pathlib import Path

from nokku.lottery.kerala.winning_corpus import (
    load_winning_corpus,
    normalize_government_record,
)


def _record_with_mixed_prizes() -> dict[str, object]:
    return {
        "source": "75337",
        "draw_date": "01/08/2026",
        "lottery_name": "KARUNYA LOTTERY NO.KR-763rd DRAW",
        "parsed": {
            "lottery_name": "KARUNYA LOTTERY NO.KR-763rd DRAW",
            "draw_date": "01/08/2026",
            "prize_tiers": [
                {
                    "label": "1st Prize",
                    "amount": "10000000",
                    "entries": ["1) KO 247228 (THRISSUR)"],
                },
                {
                    "label": "Cons Prize",
                    "amount": "5000",
                    "entries": ["KN 247228 KP 247228"],
                },
                {
                    "label": "7th Prize",
                    "amount": "500",
                    "entries": ["0014 0044", "0298"],
                },
                {
                    "label": "9th Prize",
                    "amount": "100",
                    "entries": [
                        "9990",
                        "The prize winners are advised to verify the winning numbers with the results published in the Kerala",
                        "Government Gazette and surrender the winning tickets within 90 days.",
                        "Next KARUNYA Draw will be held on 08/08/2026 at",
                    ],
                },
            ],
        },
    }


def test_normalizes_all_prize_tiers_without_footer_contamination():
    result = normalize_government_record(_record_with_mixed_prizes())

    assert result.status == "success"
    assert result.prize_tiers_examined == 4
    assert result.raw_entry_lines_examined == 8
    assert result.ignored_entry_lines == 3
    assert [entry.numeric_part for entry in result.entries] == [
        "247228",
        "247228",
        "247228",
        "0014",
        "0044",
        "0298",
        "9990",
    ]
    assert [entry.series for entry in result.entries[:3]] == ["KO", "KN", "KP"]
    assert result.entries[0].draw_serial == 75337
    assert result.entries[0].lottery_code == "KR"
    assert result.entries[0].prize_tier == "1st Prize"
    assert result.entries[0].prize_amount == 10000000
    assert result.entries[3].full_number == "0014"
    assert all(entry.numeric_part != "2026" for entry in result.entries)


def test_manifest_first_loader_reads_only_declared_shards(tmp_path: Path):
    export_dir = tmp_path / "government"
    export_dir.mkdir()
    record = _record_with_mixed_prizes()

    shard = {
        "schema_version": 4,
        "domain_path": "games/chance/lottery/kerala",
        "period": "2026-08",
        "record_count": 1,
        "records": [record],
    }
    (export_dir / "2026-08.json").write_text(json.dumps(shard), encoding="utf-8")
    (export_dir / "unlisted.json").write_text(
        json.dumps({"records": [{"source": "should-not-be-read"}]}),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 4,
        "domain_path": "games/chance/lottery/kerala",
        "cutoff_date": "2026-08-29",
        "record_count": 1,
        "oldest_draw_date": "2026-08-01",
        "latest_draw_date": "2026-08-01",
        "shards": [{"period": "2026-08", "file": "2026-08.json", "record_count": 1}],
    }
    (export_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = load_winning_corpus(export_dir, manifest_filename="manifest.json")

    assert result.status == "success"
    assert result.manifest_record_count == 1
    assert result.source_records_examined == 1
    assert result.shards_examined == 1
    assert result.normalized_entry_count == 7
    assert result.ignored_entry_lines == 3
    assert result.cutoff_date.isoformat() == "2026-08-29"


def test_missing_declared_shard_is_reported_without_directory_fallback(tmp_path: Path):
    export_dir = tmp_path / "government"
    export_dir.mkdir()
    manifest = {
        "schema_version": 4,
        "domain_path": "games/chance/lottery/kerala",
        "cutoff_date": "2026-08-29",
        "record_count": 1,
        "shards": [{"period": "2026-08", "file": "missing.json", "record_count": 1}],
    }
    (export_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (export_dir / "2026-08.json").write_text(
        json.dumps({"records": [_record_with_mixed_prizes()]}),
        encoding="utf-8",
    )

    result = load_winning_corpus(export_dir, manifest_filename="manifest.json")

    assert result.status == "partial"
    assert result.entries == ()
    assert result.shards_examined == 0
    assert result.source_records_examined == 0
    assert result.failures == ("missing shard declared by manifest: missing.json",)
