from __future__ import annotations

import sys
from pathlib import Path

from collector.collect import collect
from cossse.flow import Flow, Meaning, DispositionStatus
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.memory import Memory


DOMAIN = "games/chance/lottery/kerala"
MEMORY_PATH = Path("/tmp/nokku_heartbeat2_memory.sqlite")


if len(sys.argv) < 2 or any(not arg.isdigit() for arg in sys.argv[1:]):
    raise SystemExit(
        "Usage: python tools/refresh_sources.py SOURCE_ID [SOURCE_ID ...]"
    )

sources = sys.argv[1:]

assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"

collector_adapter = CollectorAdapter(collect)
refreshed = []

for source in sources:
    need = Meaning(
        body={
            "need": "collect",
            "domain_path": DOMAIN,
            "source": source,
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
        print(f"❌ {source} | {status}")
        for event in report["execution"].get("events", []):
            print("   event:", event)
        raise AssertionError(f"Source {source} could not be refreshed safely.")

    parsed = (report.get("data") or {}).get("parsed") or {}
    draw_date = parsed.get("draw_date")
    lottery_name = parsed.get("lottery_name")

    if not draw_date or draw_date == "Unknown":
        raise AssertionError(f"Source {source}: usable draw date missing.")
    if not lottery_name or lottery_name == "Unknown":
        raise AssertionError(f"Source {source}: usable lottery name missing.")

    with Memory(MEMORY_PATH) as memory:
        preserved = Flow().encounter(
            result_meaning,
            [MemoryAdapter(memory)],
        )

        assert preserved.status == DispositionStatus.CLAIMED
        assert len(preserved.feedback) == 1
        memory_id = preserved.feedback[0].body["memory_id"]

    refreshed.append((source, draw_date, lottery_name, memory_id))
    print(f"✅ {source} | {draw_date} | {lottery_name}")

print("\n--- REFRESH SUMMARY ---")
print("refreshed:", len(refreshed))
for source, draw_date, lottery_name, memory_id in refreshed:
    print(f"   {source} | {draw_date} | {lottery_name} | {memory_id}")
print("Existing memories were not deleted; corrected experiences were appended.")
