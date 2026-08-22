from __future__ import annotations

import re
import time
from datetime import datetime

from collector.collect import collect
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
YEAR = 2020
MEMORY_PATH = living_memory_path()


def parse_draw_date(value: str):
    return datetime.strptime(value, "%d/%m/%Y").date()


def normalize_name(value: object) -> str:
    return " ".join(str(value or "").split())


def event_code(lottery_name: str) -> str:
    match = re.search(r"\b([A-Z]+-\d+)\b", lottery_name.upper())
    return match.group(1) if match else lottery_name.upper()


def discover_known_draws(memory: Memory):
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

    # Receipts are stored oldest -> newest. The latest experience for an explicit
    # source is therefore the current remembered view of that source.
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

        known[source] = {
            "memory_id": receipt["memory_id"],
            "parsed": (outcome.get("data") or {}).get("parsed") or {},
            "outcome": outcome,
        }

    return receipts, known


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


def preserve(result_meaning: Meaning) -> str:
    with Memory(MEMORY_PATH) as memory:
        disposition = Flow().encounter(result_meaning, [MemoryAdapter(memory)])
    assert disposition.status == DispositionStatus.CLAIMED
    assert len(disposition.feedback) == 1
    return disposition.feedback[0].body["memory_id"]


def main() -> int:
    print("=== NOKKU LIVING HABITAT — VERIFY MODERN 2020 MEMORY ===")
    print("memory:", MEMORY_PATH)
    print("policy: re-read every remembered modern 2020 source from Collector;")
    print("        append a corrected experience only when the parsed result differs.\n")

    assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"

    with Memory(MEMORY_PATH) as memory:
        receipts_before, known_before = discover_known_draws(memory)

    modern_sources: list[str] = []
    for source, item in known_before.items():
        if not source.isdigit():
            continue
        parsed = item["parsed"]
        draw_date_text = parsed.get("draw_date")
        if not draw_date_text or draw_date_text == "Unknown":
            continue
        try:
            draw_date = parse_draw_date(str(draw_date_text))
        except ValueError:
            continue
        if draw_date.year == YEAR:
            modern_sources.append(source)

    modern_sources.sort(key=int)
    assert modern_sources, "No remembered modern 2020 sources were found."
    print("remembered modern 2020 sources:", len(modern_sources))
    print("address range:", modern_sources[0], "→", modern_sources[-1])

    adapter = CollectorAdapter(collect)
    live_snapshots: dict[str, dict[str, object]] = {}
    corrected: list[tuple[str, str, str, str, str, str]] = []

    print("\n1. Revalidating against live Collector...\n")
    for index, source in enumerate(modern_sources, start=1):
        remembered = dict(known_before[source]["parsed"])
        result_meaning = collect_source(adapter, source)
        report = result_meaning.body["outcome"]
        status = report["execution"]["status"]

        if status not in ("success", "partial"):
            print("\n❌ MODERN SOURCE VERIFICATION FAILURE")
            print("   source:", source)
            print("   status:", status)
            for event in report["execution"].get("events", []):
                print("   event:", event)
            raise AssertionError("Stopped safely at first unverifiable modern source.")

        live = dict((report.get("data") or {}).get("parsed") or {})
        live_date_text = str(live.get("draw_date") or "")
        live_name = normalize_name(live.get("lottery_name"))
        assert live_date_text and live_date_text != "Unknown", (
            f"{source}: live Collector returned no usable draw date."
        )
        live_date = parse_draw_date(live_date_text)
        assert live_date.year == YEAR, (
            f"{source}: remembered as {YEAR}, but live source now parses as {live_date}."
        )
        assert live_name and live_name != "Unknown", (
            f"{source}: live Collector returned no usable lottery name."
        )

        live_snapshots[source] = live

        if remembered == live:
            print(
                f"   [{index:02d}/{len(modern_sources):02d}] {source} | "
                f"{live_date.isoformat()} | {event_code(live_name)} | OK"
            )
            time.sleep(0.08)
            continue

        old_date = str(remembered.get("draw_date") or "Unknown")
        old_name = normalize_name(remembered.get("lottery_name"))
        memory_id = preserve(result_meaning)
        corrected.append(
            (
                source,
                old_date,
                event_code(old_name),
                live_date_text,
                event_code(live_name),
                memory_id,
            )
        )
        print(
            f"   [{index:02d}/{len(modern_sources):02d}] {source} | CORRECTED | "
            f"{old_date} {event_code(old_name)} → "
            f"{live_date_text} {event_code(live_name)}"
        )
        time.sleep(0.08)

    print("\n2. Restarting Nokku/Memory...")
    with Memory(MEMORY_PATH) as memory:
        receipts_after, known_after = discover_known_draws(memory)

    for source, expected in live_snapshots.items():
        recalled = known_after.get(source)
        assert recalled is not None, f"Restart recall lost modern source {source}."
        assert recalled["parsed"] == expected, (
            f"Restart recall did not retain the live corrected result for {source}."
        )

    print("\n--- MODERN 2020 MEMORY VERIFICATION SUMMARY ---")
    print("verified sources:", len(modern_sources))
    print("corrected sources:", len(corrected))
    for source, old_date, old_code, new_date, new_code, memory_id in corrected:
        print(
            f"   {source} | {old_date} {old_code} → "
            f"{new_date} {new_code} | {memory_id}"
        )
    print("receipts before:", len(receipts_before))
    print("receipts after:", len(receipts_after))
    print("restart recall matches live Collector: YES")
    print("existing memories deleted: NO")
    print("\n✅ PASSED — modern 2020 Memory verified against live Collector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
