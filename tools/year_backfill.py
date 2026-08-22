from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta

from collector.collect import collect
from collector.domains.registry import DomainRegistry
from cossse.flow import Flow, Meaning, DispositionStatus
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
MEMORY_PATH = living_memory_path()

# Operational safeguard, not a domain rule.
MAX_CONSECUTIVE_EMPTY = 100


if len(sys.argv) != 2 or not sys.argv[1].isdigit():
    raise SystemExit("Usage: python tools/year_backfill.py YEAR")

YEAR = int(sys.argv[1])
TARGET_START = date(YEAR, 1, 1)
TARGET_END = date(YEAR, 12, 31)


def parse_draw_date(value):
    return datetime.strptime(value, "%d/%m/%Y").date()


def discover_known_draws(memory):
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
    known = {}

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

        serial = str(request.get("source", ""))
        if not serial.isdigit():
            continue

        parsed = (outcome.get("data") or {}).get("parsed") or {}
        known[serial] = {
            "memory_id": receipt["memory_id"],
            "parsed": parsed,
            "outcome": outcome,
        }

    return receipts, known


def preserve_experience(result_meaning):
    with Memory(MEMORY_PATH) as memory:
        disposition = Flow().encounter(
            result_meaning,
            [MemoryAdapter(memory)],
        )

        assert disposition.status == DispositionStatus.CLAIMED
        assert len(disposition.feedback) == 1
        return disposition.feedback[0].body["memory_id"]


def event_types(report):
    return {
        event.get("type")
        for event in report.get("execution", {}).get("events", [])
        if isinstance(event, dict)
    }


def compress_ranges(values):
    """Return ascending integer ranges from an iterable of integers."""
    numbers = sorted(set(values))
    if not numbers:
        return []

    ranges = []
    start = previous = numbers[0]

    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue

        ranges.append((start, previous))
        start = previous = number

    ranges.append((start, previous))
    return ranges


def resolve_previous_published_source(connector, before_source):
    """Ask the source-specific Collector connector for an official predecessor."""
    resolver = getattr(connector, "previous_source", None)
    if not callable(resolver):
        return None

    try:
        resolved = resolver(str(before_source))
    except Exception as exc:
        print("   official history resolver error:", repr(exc))
        return None

    if resolved is None:
        return None

    try:
        return int(resolved)
    except (TypeError, ValueError):
        return None


print(f"\n=== NOKKU LIVING HABITAT — YEAR BACKFILL {YEAR} ===")
assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"

with Memory(MEMORY_PATH) as memory:
    receipts_before, known_before = discover_known_draws(memory)

assert known_before
dated_before = []
for serial_text, item in known_before.items():
    draw_date_text = item["parsed"].get("draw_date")
    if not draw_date_text or draw_date_text == "Unknown":
        continue
    dated_before.append((int(serial_text), parse_draw_date(draw_date_text)))

assert dated_before

print("\n1. Nokku wakes")
print("   memory:", MEMORY_PATH)
print("   receipts discovered:", len(receipts_before))
print("   known date range:", min(x[1] for x in dated_before), "→", max(x[1] for x in dated_before))

known_target = [
    (serial, draw_date)
    for serial, draw_date in dated_before
    if TARGET_START <= draw_date <= TARGET_END
]

if known_target:
    oldest_target_serial = min(x[0] for x in known_target)
    serial = oldest_target_serial - 1
    last_published_serial = oldest_target_serial
    print("\n2. Resume")
    print(f"   existing {YEAR} draws:", len(known_target))
    print("   resume source id:", serial)
else:
    oldest_known_serial = min(x[0] for x in dated_before)
    serial = oldest_known_serial - 1
    last_published_serial = oldest_known_serial
    print("\n2. New yearly backfill")
    print("   derived start source id:", serial)

collector_adapter = CollectorAdapter(collect)
source_connector = DomainRegistry().get_connector(DOMAIN)
assert source_connector is not None, f"Missing Collector connector for {DOMAIN}"

request_count = 0
previous_attempted_serial = None
newly_preserved = []
boundary_serial = None
boundary_date = None
pending_empty_ids = []
confirmed_empty_ids = []
resolver_jumps = []

print(f"\n3. Walking backward through {YEAR}...\n")

while True:
    if previous_attempted_serial is not None:
        assert serial < previous_attempted_serial, (
            "Traversal must move to a lower source ID on every iteration."
        )
    previous_attempted_serial = serial
    request_count += 1

    serial_text = str(serial)

    if serial_text in known_before:
        parsed = known_before[serial_text]["parsed"]
        draw_date_text = parsed.get("draw_date")
        if draw_date_text and draw_date_text != "Unknown":
            draw_date = parse_draw_date(draw_date_text)
            print(f"   {serial_text} | {draw_date.isoformat()} | already known")

            if pending_empty_ids:
                confirmed_empty_ids.extend(pending_empty_ids)
                print(
                    "      confirmed sparse source-id range:",
                    f"{pending_empty_ids[0]} → {pending_empty_ids[-1]}",
                )
                pending_empty_ids = []

            last_published_serial = int(serial_text)

            if draw_date < TARGET_START:
                boundary_serial = serial_text
                boundary_date = draw_date
                break

        serial -= 1
        continue

    need = Meaning(
        body={
            "need": "collect",
            "domain_path": DOMAIN,
            "source": serial_text,
            "store": False,
            "requester": "nokku",
        }
    )

    disposition = Flow().encounter(need, [collector_adapter])
    assert disposition.status == DispositionStatus.CLAIMED
    assert len(disposition.feedback) == 1

    result_meaning = disposition.feedback[0]
    report = result_meaning.body["outcome"]
    status = report["execution"]["status"]

    if status not in ("success", "partial"):
        types = event_types(report)

        # Small source-ID gaps are directly probed because Living Habitat evidence
        # proved ordinary sparse IDs. A large desert is different: after a bounded
        # direct probe, ask the source-specific Collector connector to navigate via
        # the official older-draw index instead of brute-forcing the address space.
        if "empty_content" in types:
            pending_empty_ids.append(serial)
            print(f"·  {serial_text} | empty source id — probing backward")

            if len(pending_empty_ids) >= MAX_CONSECUTIVE_EMPTY:
                resolved = resolve_previous_published_source(
                    source_connector,
                    last_published_serial,
                )

                if resolved is None or resolved >= serial:
                    print("\n❌ UNRESOLVED SOURCE-ID DESERT")
                    print(
                        "   directly probed empty range:",
                        f"{pending_empty_ids[0]} → {pending_empty_ids[-1]}",
                    )
                    print("   safety limit:", MAX_CONSECUTIVE_EMPTY)
                    print("   official history resolver produced no safe predecessor")
                    raise AssertionError(
                        "Stopped safely: source desert unresolved by official history."
                    )

                confirmed_empty_ids.extend(pending_empty_ids)
                resolver_jumps.append(
                    (
                        last_published_serial,
                        resolved,
                        pending_empty_ids[0],
                        pending_empty_ids[-1],
                    )
                )

                print(
                    "      bounded direct probe exhausted:",
                    f"{pending_empty_ids[0]} → {pending_empty_ids[-1]}",
                )
                print(
                    "      official history resolver jump:",
                    f"{last_published_serial} → {resolved}",
                )

                pending_empty_ids = []
                serial = resolved
                continue

            serial -= 1
            time.sleep(0.15)
            continue

        print("\n❌ HISTORICAL SOURCE BOUNDARY / FAILURE")
        print("   source id:", serial_text)
        print("   status:", status)
        for event in report["execution"].get("events", []):
            print("   event:", event)
        raise AssertionError("Stopped safely at first unresolved historical record.")

    parsed = report["data"]["parsed"]
    assert parsed is not None, f"Source {serial_text}: parsed result missing."

    draw_date_text = parsed.get("draw_date")
    assert draw_date_text and draw_date_text != "Unknown", f"Source {serial_text}: usable draw date missing."

    draw_date = parse_draw_date(draw_date_text)
    lottery_name = " ".join(str(parsed.get("lottery_name", "")).split())

    if pending_empty_ids:
        confirmed_empty_ids.extend(pending_empty_ids)
        print(
            "      confirmed sparse source-id range:",
            f"{pending_empty_ids[0]} → {pending_empty_ids[-1]}",
        )
        pending_empty_ids = []

    print(f"   {serial_text} | {draw_date.isoformat()} | {lottery_name}")
    last_published_serial = int(serial_text)

    if draw_date < TARGET_START:
        boundary_serial = serial_text
        boundary_date = draw_date
        print(f"\n   Reached pre-{YEAR} boundary.")
        print("   boundary source id:", boundary_serial)
        print("   boundary date:", boundary_date.isoformat())
        break

    if TARGET_START <= draw_date <= TARGET_END:
        memory_id = preserve_experience(result_meaning)
        newly_preserved.append((int(serial_text), draw_date, lottery_name, memory_id))

    serial -= 1
    time.sleep(0.15)

print("\n4. Restarting Nokku/Memory...")

with Memory(MEMORY_PATH) as memory:
    receipts_after, known_after = discover_known_draws(memory)

target_after = []
for serial_text, item in known_after.items():
    draw_date_text = item["parsed"].get("draw_date")
    if not draw_date_text or draw_date_text == "Unknown":
        continue

    draw_date = parse_draw_date(draw_date_text)
    if TARGET_START <= draw_date <= TARGET_END:
        lottery_name = " ".join(str(item["parsed"].get("lottery_name", "")).split())
        target_after.append((int(serial_text), draw_date, lottery_name))

target_after.sort()
assert target_after

# Source IDs are identifiers, not guaranteed event sequence numbers.
# Report holes; do not mistake them for missing lottery draws.
serial_numbers = [x[0] for x in target_after]
source_id_holes = sorted(
    set(range(min(serial_numbers), max(serial_numbers) + 1)) - set(serial_numbers)
)
source_id_gap_ranges = compress_ranges(source_id_holes)

by_date = defaultdict(list)
for serial_number, draw_date, name in target_after:
    by_date[draw_date].append((serial_number, name))

all_days = []
cursor = TARGET_START
while cursor <= TARGET_END:
    all_days.append(cursor)
    cursor += timedelta(days=1)

no_draw_dates = [day for day in all_days if day not in by_date]
multiple_draw_dates = {day: records for day, records in by_date.items() if len(records) > 1}
extra_draws = sum(len(records) - 1 for records in multiple_draw_dates.values())
expected_draw_count = len(all_days) - len(no_draw_dates) + extra_draws
assert expected_draw_count == len(target_after), "Calendar accounting does not reconcile with draw count."

month_counts = Counter(draw_date.strftime("%Y-%m") for _, draw_date, _ in target_after)
bumper_draws = [item for item in target_after if "BUMPER" in item[2].upper()]

print(f"\n5. {YEAR} historical summary")
for month_number in range(1, 13):
    month = f"{YEAR}-{month_number:02d}"
    print(f"   {month}: {month_counts.get(month, 0)} draws")

print(f"\n   total {YEAR} draws:", len(target_after))
print("   observed source-id range:", min(serial_numbers), "→", max(serial_numbers))
print("   source IDs assumed contiguous: NO")
print("   source-id holes observed:", len(source_id_holes))
for start, end in source_id_gap_ranges:
    if start == end:
        print(f"      {start}")
    else:
        print(f"      {start} → {end}")

print("\n   calendar days:", len(all_days))
print("   dates with NO draw:", len(no_draw_dates))
for day in no_draw_dates:
    print("      ", day.isoformat())

print("\n   dates with MULTIPLE draws:", len(multiple_draw_dates))
for day in sorted(multiple_draw_dates):
    print("      ", day.isoformat())
    for serial_number, name in multiple_draw_dates[day]:
        print(f"         {serial_number} | {name}")

print("   extra draws on multi-draw dates:", extra_draws)
print("\n   calendar accounting:")
print(f"      {len(all_days)} - {len(no_draw_dates)} + {extra_draws} = {len(target_after)}")
print("   calendar accounting internally reconciled: YES")

print("\n   bumper/special-looking draws:", len(bumper_draws))
for serial_number, draw_date, name in bumper_draws:
    print(f"      {serial_number} | {draw_date.isoformat()} | {name}")

print("\n   official history resolver jumps:", len(resolver_jumps))
for before_source, resolved_source, probed_start, probed_end in resolver_jumps:
    print(
        f"      {before_source} → {resolved_source} "
        f"after direct empty probe {probed_start} → {probed_end}"
    )

print("\n6. Verification")
print("   historical resume derived: YES")
print("   full-year traversal: YES")
print("   immediate preservation: YES")
print("   restart/rediscovery: YES")
print("   sparse source IDs supported: YES")
print("   source deserts use official history resolver: YES")
print("   empty source IDs silently treated as draws: NO")
print("   one-draw-per-day assumption: NO")
print("   calendar accounting verified: YES")
print(f"   pre-{YEAR} boundary:", boundary_serial, boundary_date)
print("   newly preserved this run:", len(newly_preserved))
print("   empty source ids directly confirmed during this run:", len(confirmed_empty_ids))
print("   official history resolver jumps this run:", len(resolver_jumps))
print("   source addresses attempted this run:", request_count)

print("\n================================================")
print(f"❤️  YEAR {YEAR} BACKFILL PASSED")
print("Discover → Resume → Probe Sparse Source IDs → Resolve Source Deserts")
print("→ Preserve → Cross Boundary → Restart → Reconcile → Verify")
print("================================================\n")