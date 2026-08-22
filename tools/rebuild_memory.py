from __future__ import annotations

import sys
import time

from collector.collect import collect
from cossse.flow import Flow, Meaning, DispositionStatus
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
MEMORY_PATH = living_memory_path()
MAX_CONSECUTIVE_EMPTY = 100


if len(sys.argv) != 3 or any(not arg.isdigit() for arg in sys.argv[1:]):
    raise SystemExit("Usage: python tools/rebuild_memory.py HIGH_SOURCE_ID LOW_SOURCE_ID")

HIGH = int(sys.argv[1])
LOW = int(sys.argv[2])
if HIGH < LOW:
    HIGH, LOW = LOW, HIGH


def discover_known_sources(memory):
    flow = Flow()
    adapter = MemoryAdapter(memory)
    discovery = flow.encounter(
        Meaning(body={"need": "discover_preserved_experiences", "requester": "nokku"}),
        [adapter],
    )
    assert discovery.status == DispositionStatus.CLAIMED

    known = set()
    for receipt in discovery.feedback[0].body.get("receipts", []):
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
        candidate = recalled.feedback[0].body.get("value") or {}
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
        if source.isdigit():
            known.add(int(source))
    return known


def event_types(report):
    return {
        event.get("type")
        for event in report.get("execution", {}).get("events", [])
        if isinstance(event, dict)
    }


print("\n=== NOKKU LIVING MEMORY RECOVERY ===")
print("memory:", MEMORY_PATH)
print("source range:", HIGH, "→", LOW)
print("mode: resumable authoritative-source reconstruction")

with Memory(MEMORY_PATH) as memory:
    known_before = discover_known_sources(memory)

print("known sources before recovery:", len(known_before))

collector_adapter = CollectorAdapter(collect)
newly_preserved = 0
already_known = 0
empty_ids = []
consecutive_empty = 0

for source in range(HIGH, LOW - 1, -1):
    if source in known_before:
        already_known += 1
        continue

    source_text = str(source)
    need = Meaning(
        body={
            "need": "collect",
            "domain_path": DOMAIN,
            "source": source_text,
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
        if "empty_content" in types:
            empty_ids.append(source)
            consecutive_empty += 1
            print(f"· {source_text} | empty source id")
            if consecutive_empty > MAX_CONSECUTIVE_EMPTY:
                raise AssertionError(
                    f"Stopped safely after more than {MAX_CONSECUTIVE_EMPTY} consecutive empty source IDs."
                )
            time.sleep(0.05)
            continue

        print("\n❌ RECOVERY STOPPED")
        print("source:", source_text)
        print("status:", status)
        for event in report["execution"].get("events", []):
            print("event:", event)
        raise AssertionError("Stopped safely at first non-empty-content source failure.")

    consecutive_empty = 0
    parsed = (report.get("data") or {}).get("parsed") or {}
    draw_date = parsed.get("draw_date")
    lottery_name = parsed.get("lottery_name")

    if not draw_date or draw_date == "Unknown":
        raise AssertionError(f"Source {source_text}: usable draw date missing.")
    if not lottery_name or lottery_name == "Unknown":
        raise AssertionError(f"Source {source_text}: usable lottery name missing.")

    with Memory(MEMORY_PATH) as memory:
        preserved = Flow().encounter(result_meaning, [MemoryAdapter(memory)])
        assert preserved.status == DispositionStatus.CLAIMED
        assert len(preserved.feedback) == 1

    newly_preserved += 1
    print(f"✅ {source_text} | {draw_date} | {lottery_name}")
    time.sleep(0.05)

with Memory(MEMORY_PATH) as memory:
    known_after = discover_known_sources(memory)

print("\n--- RECOVERY SUMMARY ---")
print("memory:", MEMORY_PATH)
print("range:", HIGH, "→", LOW)
print("already known:", already_known)
print("newly preserved:", newly_preserved)
print("empty source ids observed:", len(empty_ids))
print("known sources after recovery:", len(known_after))
print("restart/rediscovery: YES")
print("Recovery is resumable: rerunning skips sources already preserved.")
print("================================================\n")
