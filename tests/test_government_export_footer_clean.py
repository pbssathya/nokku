"""Guard the canonical Kerala Government export against prize-footer contamination."""

from __future__ import annotations

import json
from pathlib import Path


EXPORT_ROOT = Path("exports/kerala_lottery_government")
FOOTER_MARKERS = (
    "government gazette",
    "prize winners are advised",
    "surrender the winning tickets",
    "deputy director",
    "directorate of state lotteries",
    "gorky bhavan",
    "digitally signed document",
    "authenticity may be",
    "verified through",
    "veriﬁed through",
    "sd/-",
)


def _is_footer_entry(value: object) -> bool:
    text = str(value or "").strip().lower()
    if any(marker in text for marker in FOOTER_MARKERS):
        return True
    return text.startswith("next ") and " draw will be held on" in text


def test_canonical_government_export_has_no_prize_footer_contamination() -> None:
    manifest = json.loads((EXPORT_ROOT / "manifest.json").read_text(encoding="utf-8"))
    contaminated: list[tuple[str, str]] = []

    for shard_info in manifest["shards"]:
        shard = json.loads((EXPORT_ROOT / shard_info["file"]).read_text(encoding="utf-8"))
        for record in shard["records"]:
            source = str(record.get("source") or "")
            for tier in (record.get("parsed") or {}).get("prize_tiers") or []:
                for entry in tier.get("entries") or []:
                    if _is_footer_entry(entry):
                        contaminated.append((source, str(entry)))

    assert contaminated == []
