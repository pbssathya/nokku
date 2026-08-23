from __future__ import annotations

import re
from datetime import date, datetime

from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
MEMORY_PATH = living_memory_path()
TARGET_PREFIX = "NR"
CODE_RE = re.compile(
    r"LOTTERY\s+NO\.\s*([A-Z]+)-(\d+)(?:ST|ND|RD|TH)?\b",
    flags=re.I,
)


def parse_draw_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def normalize_name(value: object) -> str:
    return " ".join(str(value or "").split())


def discover_known(memory: Memory):
    flow = Flow()
    adapter = MemoryAdapter(memory)
    discovery = flow.encounter(
        Meaning(body={"need": "discover_preserved_experiences", "requester": "nokku"}),
        [adapter],
    )
    assert discovery.status == DispositionStatus.CLAIMED
    assert len(discovery.feedback) == 1

    known: dict[str, dict[str, object]] = {}
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
        if not source:
            continue
        known[source] = (outcome.get("data") or {}).get("parsed") or {}

    return known


def legacy_drawno(source: str):
    if not source.startswith("legacy:"):
        return None
    raw = source.split(":", 1)[1]
    return int(raw) if raw.isdigit() else None


def main() -> int:
    print("=== NOKKU READ-ONLY NR FAMILY SOURCE-ORDER AUDIT ===")
    print("preservation: NO")
    print("network retrieval: NO")
    print("purpose: test whether remembered NR source addresses preserve family-local sequence order")

    assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"
    with Memory(MEMORY_PATH) as memory:
        known = discover_known(memory)

    records = []
    for source, parsed in known.items():
        name = normalize_name(parsed.get("lottery_name"))
        match = CODE_RE.search(name.upper())
        if not match or match.group(1).upper() != TARGET_PREFIX:
            continue

        drawno = legacy_drawno(source)
        if drawno is None:
            continue

        draw_date_text = str(parsed.get("draw_date") or "")
        if not draw_date_text or draw_date_text == "Unknown":
            continue
        try:
            draw_date = parse_draw_date(draw_date_text)
        except ValueError:
            continue

        sequence = int(match.group(2))
        records.append((sequence, draw_date, drawno, source, name))

    records.sort(key=lambda item: item[0])
    print("remembered NR records:", len(records))

    if not records:
        print("No NR records available.")
        return 0

    print("\n2017 NR sequence rows")
    target_rows = [row for row in records if row[1].year == 2017]
    for sequence, draw_date, drawno, source, name in target_rows:
        print(f"   NR-{sequence:02d} | {draw_date.isoformat()} | {source} | drawno={drawno} | {name}")

    comparable_pairs = 0
    increasing_pairs = 0
    inversions = []

    for left, right in zip(records, records[1:]):
        left_seq, left_date, left_drawno, left_source, _ = left
        right_seq, right_date, right_drawno, right_source, _ = right
        if right_seq <= left_seq:
            continue
        comparable_pairs += 1
        if right_drawno > left_drawno:
            increasing_pairs += 1
        else:
            inversions.append(
                (
                    left_seq,
                    left_date,
                    left_source,
                    left_drawno,
                    right_seq,
                    right_date,
                    right_source,
                    right_drawno,
                )
            )

    by_sequence = {row[0]: row for row in records}
    nr12 = by_sequence.get(12)
    nr14 = by_sequence.get(14)

    print("\n=== NR FAMILY SOURCE-ORDER AUDIT SUMMARY ===")
    print("comparable sequence pairs:", comparable_pairs)
    print("pairs with increasing legacy drawno:", increasing_pairs)
    print("family-local address inversions:", len(inversions))
    for item in inversions[:20]:
        (
            left_seq,
            left_date,
            left_source,
            left_drawno,
            right_seq,
            right_date,
            right_source,
            right_drawno,
        ) = item
        print(
            f"   NR-{left_seq} {left_date.isoformat()} {left_source} ({left_drawno}) -> "
            f"NR-{right_seq} {right_date.isoformat()} {right_source} ({right_drawno})"
        )

    if nr12 and nr14:
        print(
            "NR-12/NR-14 bracket:",
            nr12[3],
            "->",
            nr14[3],
            f"({nr12[2]} -> {nr14[2]})",
        )
        print("NR-13 remembered:", "YES" if 13 in by_sequence else "NO")
    else:
        print("NR-12/NR-14 bracket: unavailable")

    monotonic = comparable_pairs > 0 and not inversions
    print("family-local source order monotonic in remembered evidence:", "YES" if monotonic else "NO")
    print("NR-13 existence proven:", "NO")
    print("Memory changed: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
