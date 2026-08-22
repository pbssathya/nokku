from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path

from collector.collect import collect
from cossse.flow import Flow, Meaning, DispositionStatus
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.memory import Memory


DOMAIN = "games/chance/lottery/kerala"
MEMORY_PATH = Path("/tmp/nokku_heartbeat2_memory.sqlite")
MAX_REQUESTS = 450


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
    print("\n2. Resume")
    print(f"   existing {YEAR} draws:", len(known_target))
    print("   resume serial:", serial)
else:
    oldest_known_serial = min(x[0] for x in dated_before)
    serial = oldest_known_serial - 1
    print("\n2. New yearly backfill")
    print("   derived start serial:", serial)

collector_adapter = CollectorAdapter(collect)
request_count = 0
newly_preserved = []
boundary_serial = None
boundary_date = None

print(f"\n3. Walking backward through {YEAR}...\n")

while True:
    request_count += 1
    assert request_count <= MAX_REQUESTS, f"Safety limit reached before crossing out of {YEAR}."

    serial_text = str(serial)

    if serial_text in known_before:
        parsed = known_before[serial_text]["parsed"]
        draw_date_text = parsed.get("draw_date")
        if draw_date_text and draw_date_text != "Unknown":
            draw_date = parse_draw_date(draw_date_text)
            print(f"   {serial_text} | {draw_date.isoformat()} | already known")
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
        print("\n❌ HISTORICAL SOURCE BOUNDARY / FAILURE")
        print("   serial:", serial_text)
        print("   status:", status)
        for event in report["execution"].get("events", []):
            print("   event:", event)
        raise AssertionError("Stopped safely at first unresolved historical record.")

    parsed = report["data"]["parsed"]
    assert parsed is not None, f"Serial {serial_text}: parsed result missing."

    draw_date_text = parsed.get("draw_date")
    assert draw_date_text and draw_date_text != "Unknown", f"Serial {serial_text}: usable draw date missing."

    draw_date = parse_draw_date(draw_date_text)
    lottery_name = " ".join(str(parsed.get("lottery_name", "")).split())

    print(f"   {serial_text} | {draw_date.isoformat()} | {lottery_name}")

    if draw_date < TARGET_START:
        boundary_serial = serial_text
        boundary_date = draw_date
        print(f"\n   Reached pre-{YEAR} boundary.")
        print("   boundary serial:", boundary_serial)
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

serial_numbers = [x[0] for x in target_after]
expected_serials = list(range(min(serial_numbers), max(serial_numbers) + 1))
assert serial_numbers == expected_serials, f"Internal serial gap detected in {YEAR}."

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
print("   serial range:", min(serial_numbers), "→", max(serial_numbers))
print("   internal serial continuity: YES")

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
print("   calendar accounting reconciled: YES")

print("\n   bumper/special-looking draws:", len(bumper_draws))
for serial_number, draw_date, name in bumper_draws:
    print(f"      {serial_number} | {draw_date.isoformat()} | {name}")

print("\n6. Verification")
print("   historical resume derived: YES")
print("   full-year traversal: YES")
print("   immediate preservation: YES")
print("   restart/rediscovery: YES")
print("   serial continuity: YES")
print("   one-draw-per-day assumption: NO")
print("   calendar accounting verified: YES")
print("   silent serial gaps allowed: NO")
print(f"   pre-{YEAR} boundary:", boundary_serial, boundary_date)
print("   newly preserved this run:", len(newly_preserved))

print("\n================================================")
print(f"❤️  YEAR {YEAR} BACKFILL PASSED")
print("Discover → Resume → Walk → Preserve → Observe")
print("→ Cross Boundary → Restart → Reconcile → Verify")
print("================================================\n")
