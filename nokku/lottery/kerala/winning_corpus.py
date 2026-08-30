"""Manifest-first normalized view of Kerala Government winning-number history.

The Government export remains the preserved factual source. This module is a
consumer-side adapter: it reads only manifest-declared shards, extracts winning
number representations from every prize tier, excludes non-number/footer lines
without mutating the source export, and returns a truthful receipt.

It intentionally performs no numerology, recurrence analysis, astrology, or
BUY/SKIP policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re


KERALA_LOTTERY_DOMAIN = "games/chance/lottery/kerala"
DRAW_DATE_FORMAT = "%d/%m/%Y"

_SERIES_NUMBER_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z]{1,3})\s+(\d{4,6})(?!\d)",
    re.IGNORECASE,
)
_DIGIT_LIST_PATTERN = re.compile(
    r"^\s*(?:\d+\)\s*)?(\d{4,6}(?:\s+\d{4,6})*)\s*$"
)
_LOTTERY_CODE_PATTERN = re.compile(r"\b([A-Z]{1,5})\s*-\s*\d+", re.IGNORECASE)
_EMBEDDED_CONSOLATION_PATTERN = re.compile(
    r"\b(?:consolation|cons)\s+prize\b",
    re.IGNORECASE,
)
_AMOUNT_ONLY_PATTERN = re.compile(r"^\s*:?\s*([\d,]+)\s*/-\s*$")
_LOCATION_SUFFIX_PATTERN = re.compile(r"\([^()]+\)\s*$")


@dataclass(frozen=True, slots=True)
class WinningNumberEntry:
    """One normalized winning-number representation from Government evidence."""

    source: str
    draw_serial: int | None
    draw_date: date
    lottery_name: str
    lottery_code: str | None
    prize_tier: str
    prize_amount: int | None
    series: str | None
    full_number: str
    numeric_part: str
    raw_entry: str


@dataclass(frozen=True, slots=True)
class WinningRecordNormalizationResult:
    """Receipt for normalizing one preserved Government draw record."""

    status: str
    entries: tuple[WinningNumberEntry, ...]
    prize_tiers_examined: int
    raw_entry_lines_examined: int
    ignored_entry_lines: int
    reclassified_entry_count: int = 0
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WinningCorpusResult:
    """Receipt for a manifest-first normalized historical winning corpus."""

    status: str
    entries: tuple[WinningNumberEntry, ...]
    manifest_record_count: int
    source_records_examined: int
    shards_examined: int
    prize_tiers_examined: int
    raw_entry_lines_examined: int
    ignored_entry_lines: int
    normalized_entry_count: int
    cutoff_date: date | None
    reclassified_entry_count: int = 0
    failures: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()


def _parse_draw_date(value: object) -> date | None:
    try:
        return datetime.strptime(str(value or ""), DRAW_DATE_FORMAT).date()
    except ValueError:
        return None


def _parse_iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _lottery_code(lottery_name: str) -> str | None:
    match = _LOTTERY_CODE_PATTERN.search(lottery_name)
    return match.group(1).upper() if match is not None else None


def _prize_amount(value: object) -> int | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _winner_tokens(raw_entry: object) -> tuple[tuple[str | None, str], ...]:
    text = " ".join(str(raw_entry or "").split())
    if not text:
        return ()

    series_matches = tuple(_SERIES_NUMBER_PATTERN.finditer(text))
    if series_matches:
        return tuple(
            (match.group(1).upper(), match.group(2)) for match in series_matches
        )

    digit_list = _DIGIT_LIST_PATTERN.fullmatch(text)
    if digit_list is None:
        return ()
    return tuple((None, token) for token in digit_list.group(1).split())


def _is_first_prize(label: str) -> bool:
    return label.casefold() == "1st prize"


def _is_consolation_prize(label: str) -> bool:
    return label.casefold() in {"consolation prize", "cons prize"}


def _first_prize_amount(prize_tiers: list[object]) -> int | None:
    for tier in prize_tiers:
        if not isinstance(tier, dict):
            continue
        label = " ".join(str(tier.get("label") or "").split())
        if _is_first_prize(label):
            return _prize_amount(tier.get("amount"))
    return None


def normalize_government_record(
    record: dict[str, object],
) -> WinningRecordNormalizationResult:
    """Normalize every supported winning representation in one Government record."""
    failures: list[str] = []
    uncertainty: list[str] = []

    source = str(record.get("source") or "").strip()
    if not source:
        return WinningRecordNormalizationResult(
            status="failed",
            entries=(),
            prize_tiers_examined=0,
            raw_entry_lines_examined=0,
            ignored_entry_lines=0,
            failures=("Government record has no source",),
        )

    parsed = record.get("parsed")
    if not isinstance(parsed, dict):
        return WinningRecordNormalizationResult(
            status="failed",
            entries=(),
            prize_tiers_examined=0,
            raw_entry_lines_examined=0,
            ignored_entry_lines=0,
            failures=(f"Government record {source} has no object parsed payload",),
        )

    draw_date = _parse_draw_date(record.get("draw_date") or parsed.get("draw_date"))
    if draw_date is None:
        return WinningRecordNormalizationResult(
            status="failed",
            entries=(),
            prize_tiers_examined=0,
            raw_entry_lines_examined=0,
            ignored_entry_lines=0,
            failures=(f"Government record {source} has no usable draw date",),
        )

    lottery_name = " ".join(
        str(record.get("lottery_name") or parsed.get("lottery_name") or "").split()
    )
    if not lottery_name:
        uncertainty.append(f"Government record {source} has no lottery name")
    lottery_code = _lottery_code(lottery_name)
    if lottery_name and lottery_code is None:
        uncertainty.append(f"Government record {source} lottery code could not be derived")

    prize_tiers = parsed.get("prize_tiers")
    if not isinstance(prize_tiers, list):
        return WinningRecordNormalizationResult(
            status="failed",
            entries=(),
            prize_tiers_examined=0,
            raw_entry_lines_examined=0,
            ignored_entry_lines=0,
            failures=(f"Government record {source} has no prize_tiers list",),
            uncertainty=tuple(uncertainty),
        )

    first_prize_amount = _first_prize_amount(prize_tiers)
    normalized: list[WinningNumberEntry] = []
    tiers_examined = 0
    raw_lines_examined = 0
    ignored_lines = 0
    reclassified_entries = 0

    for tier_index, tier in enumerate(prize_tiers):
        if not isinstance(tier, dict):
            uncertainty.append(
                f"Government record {source} prize tier {tier_index} is not an object"
            )
            continue
        tiers_examined += 1
        label = " ".join(str(tier.get("label") or "").split())
        if not label:
            label = f"unlabelled_tier_{tier_index}"
            uncertainty.append(
                f"Government record {source} prize tier {tier_index} has no label"
            )
        amount = _prize_amount(tier.get("amount"))
        entries = tier.get("entries")
        if not isinstance(entries, list):
            uncertainty.append(
                f"Government record {source} prize tier {label} has no entries list"
            )
            continue

        effective_label = label
        effective_amount = amount
        embedded_consolation = False
        consolation_numbers_seen: set[str] = set()

        for raw_entry in entries:
            raw_lines_examined += 1
            text = " ".join(str(raw_entry or "").split())

            if (
                _is_first_prize(label)
                and _EMBEDDED_CONSOLATION_PATTERN.search(text) is not None
            ):
                embedded_consolation = True
                effective_label = "Consolation Prize"
                effective_amount = _prize_amount(text)
                ignored_lines += 1
                continue

            if embedded_consolation:
                amount_match = _AMOUNT_ONLY_PATTERN.fullmatch(text)
                if amount_match is not None:
                    effective_amount = int(amount_match.group(1).replace(",", ""))
                    ignored_lines += 1
                    continue

            tokens = _winner_tokens(text)
            if not tokens:
                ignored_lines += 1
                continue

            line_label = effective_label
            line_amount = effective_amount
            if (
                _is_consolation_prize(label)
                and len(tokens) == 1
                and consolation_numbers_seen
                and tokens[0][1] not in consolation_numbers_seen
                and _LOCATION_SUFFIX_PATTERN.search(text) is not None
            ):
                line_label = "1st Prize"
                line_amount = first_prize_amount

            for series, numeric_part in tokens:
                full_number = (
                    f"{series} {numeric_part}" if series is not None else numeric_part
                )
                normalized.append(
                    WinningNumberEntry(
                        source=source,
                        draw_serial=int(source) if source.isdigit() else None,
                        draw_date=draw_date,
                        lottery_name=lottery_name,
                        lottery_code=lottery_code,
                        prize_tier=line_label,
                        prize_amount=line_amount,
                        series=series,
                        full_number=full_number,
                        numeric_part=numeric_part,
                        raw_entry=text,
                    )
                )
                if line_label != label:
                    reclassified_entries += 1

            if _is_consolation_prize(label) and line_label == label:
                consolation_numbers_seen.update(numeric for _, numeric in tokens)

    if failures:
        status = "failed"
    elif uncertainty:
        status = "partial"
    else:
        status = "success"

    return WinningRecordNormalizationResult(
        status=status,
        entries=tuple(normalized),
        prize_tiers_examined=tiers_examined,
        raw_entry_lines_examined=raw_lines_examined,
        ignored_entry_lines=ignored_lines,
        reclassified_entry_count=reclassified_entries,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )


def load_winning_corpus(
    export_directory: str | Path,
    *,
    manifest_filename: str,
) -> WinningCorpusResult:
    """Load only manifest-declared Government shards and normalize their winners."""
    export_dir = Path(export_directory)
    manifest_path = export_dir / manifest_filename
    failures: list[str] = []
    uncertainty: list[str] = []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return WinningCorpusResult(
            status="failed",
            entries=(),
            manifest_record_count=0,
            source_records_examined=0,
            shards_examined=0,
            prize_tiers_examined=0,
            raw_entry_lines_examined=0,
            ignored_entry_lines=0,
            normalized_entry_count=0,
            cutoff_date=None,
            failures=(f"manifest read failed: {exc}",),
        )

    if not isinstance(manifest, dict):
        return WinningCorpusResult(
            status="failed",
            entries=(),
            manifest_record_count=0,
            source_records_examined=0,
            shards_examined=0,
            prize_tiers_examined=0,
            raw_entry_lines_examined=0,
            ignored_entry_lines=0,
            normalized_entry_count=0,
            cutoff_date=None,
            failures=("manifest is not an object",),
        )

    if manifest.get("domain_path") != KERALA_LOTTERY_DOMAIN:
        failures.append("manifest domain_path does not identify Kerala lottery")

    cutoff_date = _parse_iso_date(manifest.get("cutoff_date"))
    if cutoff_date is None:
        uncertainty.append("manifest cutoff_date is missing or invalid")

    try:
        manifest_record_count = int(manifest.get("record_count") or 0)
    except (TypeError, ValueError):
        manifest_record_count = 0
        uncertainty.append("manifest record_count is invalid")

    shards = manifest.get("shards")
    if not isinstance(shards, list):
        return WinningCorpusResult(
            status="failed",
            entries=(),
            manifest_record_count=manifest_record_count,
            source_records_examined=0,
            shards_examined=0,
            prize_tiers_examined=0,
            raw_entry_lines_examined=0,
            ignored_entry_lines=0,
            normalized_entry_count=0,
            cutoff_date=cutoff_date,
            failures=tuple(failures + ["manifest has no shards list"]),
            uncertainty=tuple(uncertainty),
        )

    normalized: list[WinningNumberEntry] = []
    source_records_examined = 0
    shards_examined = 0
    tiers_examined = 0
    raw_lines_examined = 0
    ignored_lines = 0
    reclassified_entries = 0

    for shard_index, shard_ref in enumerate(shards):
        if not isinstance(shard_ref, dict):
            failures.append(f"manifest shard {shard_index} is not an object")
            continue
        filename = str(shard_ref.get("file") or "").strip()
        if not filename or Path(filename).name != filename:
            failures.append(f"manifest shard {shard_index} has an invalid filename")
            continue
        shard_path = export_dir / filename
        if not shard_path.exists():
            failures.append(f"missing shard declared by manifest: {filename}")
            continue
        try:
            shard_payload = json.loads(shard_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"declared shard could not be read: {filename}: {exc}")
            continue
        if not isinstance(shard_payload, dict):
            failures.append(f"declared shard is not an object: {filename}")
            continue
        records = shard_payload.get("records")
        if not isinstance(records, list):
            failures.append(f"declared shard has no records list: {filename}")
            continue

        shards_examined += 1
        for record_index, record in enumerate(records):
            source_records_examined += 1
            if not isinstance(record, dict):
                uncertainty.append(
                    f"{filename} record {record_index} is not an object"
                )
                continue
            record_result = normalize_government_record(record)
            normalized.extend(record_result.entries)
            tiers_examined += record_result.prize_tiers_examined
            raw_lines_examined += record_result.raw_entry_lines_examined
            ignored_lines += record_result.ignored_entry_lines
            reclassified_entries += record_result.reclassified_entry_count
            failures.extend(record_result.failures)
            uncertainty.extend(record_result.uncertainty)

    if source_records_examined != manifest_record_count:
        uncertainty.append(
            "manifest record_count does not match records examined from declared shards: "
            f"manifest={manifest_record_count}, examined={source_records_examined}"
        )

    if failures or uncertainty:
        status = "partial"
    else:
        status = "success"

    return WinningCorpusResult(
        status=status,
        entries=tuple(normalized),
        manifest_record_count=manifest_record_count,
        source_records_examined=source_records_examined,
        shards_examined=shards_examined,
        prize_tiers_examined=tiers_examined,
        raw_entry_lines_examined=raw_lines_examined,
        ignored_entry_lines=ignored_lines,
        normalized_entry_count=len(normalized),
        cutoff_date=cutoff_date,
        reclassified_entry_count=reclassified_entries,
        failures=tuple(failures),
        uncertainty=tuple(uncertainty),
    )
