from __future__ import annotations

import sys
import time

from collector.collect import collect


DOMAIN = "games/chance/lottery/kerala"


def usage() -> None:
    raise SystemExit(
        "Usage: python tools/probe_serials.py START_SERIAL END_SERIAL\n"
        "Example: python tools/probe_serials.py 74419 74398"
    )


if len(sys.argv) != 3:
    usage()

try:
    start = int(sys.argv[1])
    end = int(sys.argv[2])
except ValueError:
    usage()

step = -1 if start >= end else 1

print("\n=== NOKKU LIVING HABITAT — SERIAL GAP PROBE ===")
print(f"range: {start} -> {end}")
print("preservation: NO")
print("purpose: classify source-id gap without changing remembered history\n")

successes = []
failures = []

for serial in range(start, end + step, step):
    serial_text = str(serial)
    report = collect(
        DOMAIN,
        serial_text,
        store=False,
        requester="nokku-probe",
    )

    status = report["execution"]["status"]

    if status in ("success", "partial"):
        parsed = (report.get("data") or {}).get("parsed") or {}
        draw_date = parsed.get("draw_date", "Unknown")
        lottery_name = " ".join(str(parsed.get("lottery_name", "")).split())
        successes.append((serial, draw_date, lottery_name))
        print(f"✅ {serial_text} | {draw_date} | {lottery_name}")
    else:
        events = report["execution"].get("events", [])
        event_types = [str(event.get("type", "unknown")) for event in events]
        failures.append((serial, status, event_types))
        event_text = ", ".join(event_types) if event_types else "no_event"
        print(f"·  {serial_text} | {status} | {event_text}")

    time.sleep(0.10)

print("\n--- PROBE SUMMARY ---")
print("successes:", len(successes))
print("failures:", len(failures))

if successes:
    print("\nsuccessful source ids:")
    for serial, draw_date, lottery_name in successes:
        print(f"   {serial} | {draw_date} | {lottery_name}")

if failures:
    print("\nfailed source-id ranges:")
    failed_serials = [serial for serial, _, _ in failures]
    groups = []
    group = [failed_serials[0]]

    for value in failed_serials[1:]:
        if value == group[-1] + step:
            group.append(value)
        else:
            groups.append(group)
            group = [value]
    groups.append(group)

    for group in groups:
        if len(group) == 1:
            print(f"   {group[0]}")
        else:
            print(f"   {group[0]} -> {group[-1]}")

print("\nNo records were preserved by this probe.")
print("================================================\n")
