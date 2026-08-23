from __future__ import annotations

import re
from datetime import datetime

from collector.collect import collect
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
MEMORY_PATH = living_memory_path()
CODE_RE = re.compile(
    r"LOTTERY\s+NO\.\s*([A-Z]+)-(\d+)(?:ST|ND|RD|TH)?\b",
    flags=re.I,
)

# Facts independently verified through the official direct legacy transport by
# read-only sequence-gap probes. Add only evidence-proven gaps here.
VERIFIED = {
    "legacy:56242": ("2017-06-28", "AK", 299),
}


def known_sources(memory: Memory) -> set[str]:
    flow = Flow()
    adapter = MemoryAdapter(memory)
    discovery = flow.encounter(
        Meaning(body={"need": "discover_preserved_experiences", "requester": "nokku"}),
        [adapter],
    )
    assert discovery.status == DispositionStatus.CLAIMED
    assert len(discovery.feedback) == 1

    sources: set[str] = set()
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
        assert len(recalled.feedback) == 1
        candidate = recalled.feedback[0].body.get("value") or {}
        body = candidate.get("body", {})
        if body.get("experience") != "capability_attempt" or body.get("capability") != "collect":
            continue
        outcome = body.get("outcome") or {}
        request = outcome.get("request") or {}
        if request.get("domain_path") != DOMAIN:
            continue
        source = str(request.get("source", ""))
        if source:
            sources.add(source)
    return sources


def collect_source(source: str) -> Meaning:
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
        [CollectorAdapter(collect)],
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
    print("=== NOKKU VERIFIED 2017 LEGACY-GAP PRESERVATION ===")
    print("scope: only independently verified official legacy sources")
    assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"

    with Memory(MEMORY_PATH) as memory:
        before = known_sources(memory)

    preserved: list[tuple[str, str]] = []
    skipped: list[str] = []

    for source, (expected_date, expected_prefix, expected_sequence) in VERIFIED.items():
        if source in before:
            print("ALREADY KNOWN:", source)
            skipped.append(source)
            continue

        meaning = collect_source(source)
        report = meaning.body["outcome"]
        status = report["execution"]["status"]
        assert status in ("success", "partial"), f"{source}: collection status {status}"

        parsed = (report.get("data") or {}).get("parsed") or {}
        draw_date_text = str(parsed.get("draw_date") or "")
        name = " ".join(str(parsed.get("lottery_name") or "").split())

        draw_date = datetime.strptime(draw_date_text, "%d/%m/%Y").date().isoformat()
        match = CODE_RE.search(name.upper())
        assert match, f"{source}: canonical draw code not found in {name!r}"
        prefix = match.group(1).upper()
        sequence = int(match.group(2))

        assert draw_date == expected_date, (
            f"{source}: expected {expected_date}, got {draw_date}"
        )
        assert (prefix, sequence) == (expected_prefix, expected_sequence), (
            f"{source}: expected {expected_prefix}-{expected_sequence}, got {prefix}-{sequence}"
        )

        memory_id = preserve(meaning)
        preserved.append((source, memory_id))
        print("PRESERVED:", source, "|", draw_date, "|", f"{prefix}-{sequence}", "|", name)

    with Memory(MEMORY_PATH) as memory:
        after = known_sources(memory)

    missing = [source for source, _memory_id in preserved if source not in after]
    assert not missing, f"Restart recall missing preserved sources: {missing}"

    print("\n=== VERIFIED-GAP PRESERVATION SUMMARY ===")
    print("newly preserved:", len(preserved))
    print("already known:", len(skipped))
    print("restart recall: YES")
    print("unresolved NR-13 preserved: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
