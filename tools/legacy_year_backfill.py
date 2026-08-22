from __future__ import annotations

import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from collector.collect import collect
from collector.domains.registry import DomainRegistry
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
MEMORY_PATH = living_memory_path()


if len(sys.argv) != 2 or not sys.argv[1].isdigit():
    raise SystemExit("Usage: python tools/legacy_year_backfill.py YEAR")

YEAR = int(sys.argv[1])
if YEAR >= 2021:
    raise SystemExit(
        "Legacy source-aware backfill is for 2020 and earlier. "
        "Use tools/year_backfill.py for 2021+ modern drawserial years."
    )

TARGET_START = date(YEAR, 1, 1)
TARGET_END = date(YEAR, 12, 31)


def parse_draw_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def normalize_name(value: object) -> str:
    return " ".join(str(value or "").split())


def event_code(lottery_name: str) -> str:
    """Return the published draw code for duplicate-event validation."""
    match = re.search(r"\b([A-Z]+-\d+)\b", lottery_name.upper())
    return match.group(1) if match else lottery_name.upper()


def discover_known_draws(memory: Memory):
    """Recall Kerala collect experiences without assuming one source namespace."""
    flow = Flow()
    adapter = MemoryAdapter(memory)

    discovery = flow.encounter(
        Meaning(
            body={
                "need": "discover_preserved_experiences",
                "requester": "nokku",
            }
        ),
        [adapter],
    )

    assert discovery.status == DispositionStatus.CLAIMED
    assert len(discovery.feedback) == 1

    receipts = discovery.feedback[0].body.get("receipts", [])
    known: dict[str, dict[str, object]] = {}

    # Receipts are recalled in stored order. Later corrected/repeated experiences
    # therefore replace earlier ones for the same explicit source address.
    for receipt in receipts:
        recalled = flow.encounter(
            Meaning(
                body={
                    "need": "recall_preserved_experience",
                    "memory_id": receipt["memory_id"],
                    "requester": "nokku",
                }
            ),
            [adapter],
        )

        assert recalled.status == DispositionStatus.CLAIMED
        assert len(recalled.feedback) == 1

        candidate = recalled.feedback[0].body.get("value")
        if not candidate:
            continue

        body = candidate.get("body", {})
        if body.get("experience") != "capability_attempt":
            continue
        if body.get("capability") != "collect":
            continue

        outcome = body.get("outcome") or {}
        request = outcome.get("request") or {}
        if request.get("domain_path") != DOMAIN:
            continue

        source = str(request.get("source", ""))
        if not source:
            continue

        parsed = (outcome.get("data") or {}).get("parsed") or {}
        known[source] = {
            "memory_id": receipt["memory_id"],
            "parsed": parsed,
            "outcome": outcome,
        }

    return receipts, known


def target_records(known: dict[str, dict[str, object]]):
    records: list[tuple[str, date, str]] = []
    for source, item in known.items():
        parsed = item["parsed"]
        draw_date_text = parsed.get("draw_date")
        if not draw_date_text or draw_date_text == "Unknown":
            continue

        try:
            draw_date = parse_draw_date(str(draw_date_text))
        except ValueError:
            continue

        if TARGET_START <= draw_date <= TARGET_END:
            records.append((source, draw_date, normalize_name(parsed.get("lottery_name"))))

    return records


def collect_source(adapter: CollectorAdapter, source: str) -> Meaning:
    disposition = Flow().encounter(
        Meaning(
            body={
                "need": "collect",
                "domain_path": DOMAIN,
                "source": source,
                "store": False,
                "requester": "nokku",
            }
        ),
        [adapter],
    )

    assert disposition.status == DispositionStatus.CLAIMED
    assert len(disposition.feedback) == 1
    return disposition.feedback[0]


def preserve_experience(result_meaning: Meaning) -> str:
    with Memory(MEMORY_PATH) as memory:
        disposition = Flow().encounter(result_meaning, [MemoryAdapter(memory)])

    assert disposition.status == DispositionStatus.CLAIMED
    assert len(disposition.feedback) == 1
    return disposition.feedback[0].body["memory_id"]


def main() -> int:
    print(f"\n=== NOKKU LIVING HABITAT — LEGACY SOURCE-AWARE {YEAR} BACKFILL ===")
    assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"

    connector = DomainRegistry().get_connector(DOMAIN)
    assert connector is not None, f"Missing Collector connector for {DOMAIN}"

    discover_legacy = getattr(connector, "legacy_sources_for_year", None)
    assert callable(discover_legacy), (
        "Collector does not expose legacy_sources_for_year(). "
        "Update Collector main before running this backfill."
    )

    with Memory(MEMORY_PATH) as memory:
        receipts_before, known_before = discover_known_draws(memory)

    existing_target = target_records(known_before)
    existing_legacy = [item for item in existing_target if item[0].startswith("legacy:")]
    existing_other = [item for item in existing_target if not item[0].startswith("legacy:")]

    print("\n1. Nokku wakes")
    print("   memory:", MEMORY_PATH)
    print("   receipts discovered:", len(receipts_before))
    print(f"   existing {YEAR} legacy records:", len(existing_legacy))
    print(f"   existing {YEAR} other-source records:", len(existing_other))

    print("\n2. Asking Collector for the official legacy source set...")
    legacy_sources = list(discover_legacy(YEAR))
    assert legacy_sources, f"Collector discovered no official legacy sources for {YEAR}."
    assert len(legacy_sources) == len(set(legacy_sources)), (
        "Legacy source discovery returned duplicate addresses."
    )
    assert all(source.startswith("legacy:") for source in legacy_sources)

    print("   official legacy sources:", len(legacy_sources))
    print("   first:", legacy_sources[:3])
    print("   last:", legacy_sources[-3:])

    collector_adapter = CollectorAdapter(collect)
    newly_preserved: list[tuple[str, date, str, str]] = []
    skipped_known = 0

    print("\n3. Collecting only missing legacy experiences...\n")
    for index, source in enumerate(legacy_sources, start=1):
        known_item = known_before.get(source)
        if known_item:
            parsed = known_item["parsed"]
            draw_date_text = parsed.get("draw_date")
            if draw_date_text and draw_date_text != "Unknown":
                try:
                    draw_date = parse_draw_date(str(draw_date_text))
                except ValueError:
                    draw_date = None
                if draw_date and draw_date.year == YEAR:
                    skipped_known += 1
                    print(
                        f"   [{index:03d}/{len(legacy_sources):03d}] "
                        f"{source} | already known"
                    )
                    continue

        result_meaning = collect_source(collector_adapter, source)
        report = result_meaning.body["outcome"]
        status = report["execution"]["status"]

        if status not in ("success", "partial"):
            print("\n❌ LEGACY COLLECTION FAILURE")
            print("   source:", source)
            print("   status:", status)
            for event in report["execution"].get("events", []):
                print("   event:", event)
            raise AssertionError("Stopped safely at the first unresolved legacy source.")

        parsed = (report.get("data") or {}).get("parsed") or {}
        draw_date_text = parsed.get("draw_date")
        assert draw_date_text and draw_date_text != "Unknown", (
            f"{source}: usable draw date missing."
        )

        draw_date = parse_draw_date(str(draw_date_text))
        assert draw_date.year == YEAR, (
            f"{source}: Collector discovered it for {YEAR} but parsed {draw_date}."
        )

        lottery_name = normalize_name(parsed.get("lottery_name"))
        memory_id = preserve_experience(result_meaning)
        newly_preserved.append((source, draw_date, lottery_name, memory_id))
        print(
            f"   [{index:03d}/{len(legacy_sources):03d}] "
            f"{source} | {draw_date.isoformat()} | {lottery_name}"
        )
        time.sleep(0.10)

    print("\n4. Restarting Nokku/Memory...")
    with Memory(MEMORY_PATH) as memory:
        receipts_after, known_after = discover_known_draws(memory)

    target_after = target_records(known_after)
    legacy_after = {
        source: (draw_date, name)
        for source, draw_date, name in target_after
        if source.startswith("legacy:")
    }

    missing_after = [source for source in legacy_sources if source not in legacy_after]
    assert not missing_after, f"Restart recall missing legacy sources: {missing_after[:10]}"

    # Event identity is calendar date + published draw code. Source addresses are
    # provenance, not event identity, so any duplicate must be surfaced explicitly.
    by_identity: dict[tuple[date, str], list[str]] = defaultdict(list)
    for source, draw_date, name in target_after:
        by_identity[(draw_date, event_code(name))].append(source)

    duplicate_events = {
        identity: sources
        for identity, sources in by_identity.items()
        if len(set(sources)) > 1
    }
    assert not duplicate_events, (
        "Exact event duplication appeared across source addresses: "
        f"{duplicate_events}"
    )

    by_date: dict[date, list[tuple[str, str]]] = defaultdict(list)
    for source, draw_date, name in target_after:
        by_date[draw_date].append((source, name))

    all_days: list[date] = []
    cursor = TARGET_START
    while cursor <= TARGET_END:
        all_days.append(cursor)
        cursor += timedelta(days=1)

    no_draw_dates = [day for day in all_days if day not in by_date]
    multiple_draw_dates = {
        day: records for day, records in by_date.items() if len(records) > 1
    }
    extra_draws = sum(len(records) - 1 for records in multiple_draw_dates.values())
    expected = len(all_days) - len(no_draw_dates) + extra_draws
    assert expected == len(target_after), "Calendar accounting does not reconcile."

    month_counts = Counter(draw_date.strftime("%Y-%m") for _, draw_date, _ in target_after)
    bumper_draws = [item for item in target_after if "BUMPER" in item[2].upper()]
    legacy_numbers = sorted(int(source.split(":", 1)[1]) for source in legacy_sources)

    print(f"\n5. {YEAR} historical summary")
    for month_number in range(1, 13):
        month = f"{YEAR}-{month_number:02d}"
        print(f"   {month}: {month_counts.get(month, 0)} draws")

    print(f"\n   total {YEAR} draws:", len(target_after))
    print(
        "   legacy drawno address range:",
        min(legacy_numbers),
        "→",
        max(legacy_numbers),
        "(address range only; NOT chronology)",
    )
    print("   official legacy sources:", len(legacy_sources))
    print("   exact cross-source event duplicates:", len(duplicate_events))

    print("\n   dates with NO draw:", len(no_draw_dates))
    for day in no_draw_dates:
        print("      ", day.isoformat())

    print("\n   dates with MULTIPLE draws:", len(multiple_draw_dates))
    for day in sorted(multiple_draw_dates):
        print("      ", day.isoformat())
        for source, name in multiple_draw_dates[day]:
            print(f"         {source} | {name}")

    print("\n   bumper/special-looking draws:", len(bumper_draws))
    for source, draw_date, name in sorted(bumper_draws, key=lambda item: item[1]):
        print(f"      {source} | {draw_date.isoformat()} | {name}")

    print(f"\n   pre-{YEAR} boundary:")
    print("      established per official legacy lottery family during source discovery;")
    print("      no single global legacy drawno boundary is assumed.")

    print("\n6. Verification")
    print("   legacy source discovery: YES")
    print("   missing-only collection: YES")
    print("   immediate preservation: YES")
    print("   restart recall: YES")
    print("   source addresses kept explicit: YES")
    print("   exact event duplication detected: NO")
    print("   calendar accounting internally reconciled: YES")
    print("   receipts before:", len(receipts_before))
    print("   receipts after:", len(receipts_after))
    print("   legacy already known before run:", skipped_known)
    print("   newly preserved legacy records:", len(newly_preserved))

    print(f"\n✅ PASSED — legacy source-aware {YEAR} backfill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
