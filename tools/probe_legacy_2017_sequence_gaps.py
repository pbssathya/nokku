from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime

from collector.domains.registry import DomainRegistry
from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
YEAR = 2017
MEMORY_PATH = living_memory_path()
BUFFER = 150
MAX_CANDIDATES_PER_GAP = 700
SPECIAL_PREFIXES = {"BR"}
CODE_RE = re.compile(
    r"LOTTERY\s+NO\.\s*([A-Z]+)-(\d+)(?:ST|ND|RD|TH)?\b",
    flags=re.I,
)


def parse_draw_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def normalize_name(value: object) -> str:
    return " ".join(str(value or "").split())


def decode_code(name: str):
    match = CODE_RE.search(name.upper())
    if not match:
        return None, None
    return match.group(1), int(match.group(2))


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

        candidate = recalled.feedback[0].body.get("value")
        if not candidate:
            continue
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

        parsed = (outcome.get("data") or {}).get("parsed") or {}
        known[source] = {"parsed": parsed, "memory_id": receipt["memory_id"]}

    return known


def decoded_records(known):
    records = []
    for source, item in known.items():
        parsed = item["parsed"]
        draw_date_text = str(parsed.get("draw_date") or "")
        if not draw_date_text or draw_date_text == "Unknown":
            continue
        try:
            draw_date = parse_draw_date(draw_date_text)
        except ValueError:
            continue

        name = normalize_name(parsed.get("lottery_name"))
        prefix, sequence = decode_code(name)
        records.append((source, draw_date, name, prefix, sequence))
    return records


def legacy_drawno(source: str):
    if not source.startswith("legacy:"):
        return None
    raw = source.split(":", 1)[1]
    return int(raw) if raw.isdigit() else None


def bounded_candidates(lower_drawno: int, upper_drawno: int):
    anchors = (lower_drawno, upper_drawno)
    candidates: set[int] = set()

    lo = min(anchors)
    hi = max(anchors)
    if hi - lo + 1 <= MAX_CANDIDATES_PER_GAP:
        candidates.update(range(lo, hi + 1))

    for anchor in anchors:
        start = max(1, anchor - BUFFER)
        end = anchor + BUFFER
        candidates.update(range(start, end + 1))

    ordered = sorted(
        candidates,
        key=lambda value: (min(abs(value - anchor) for anchor in anchors), -value),
    )
    return ordered[:MAX_CANDIDATES_PER_GAP]


def main() -> int:
    print("=== NOKKU READ-ONLY 2017 SEQUENCE-GAP PROBE ===")
    print("preservation: NO")
    print("purpose: test only the regular-family sequence gaps exposed by the audit")
    print("special families excluded from continuity inference:", ", ".join(sorted(SPECIAL_PREFIXES)))
    print("neighbor buffer:", BUFFER, "addresses")
    print("maximum addresses inspected per gap:", MAX_CANDIDATES_PER_GAP)

    assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"
    with Memory(MEMORY_PATH) as memory:
        known = discover_known(memory)

    records = decoded_records(known)
    by_prefix: dict[str, dict[int, tuple[str, date, str]]] = defaultdict(dict)
    for source, draw_date, name, prefix, sequence in records:
        if draw_date.year != YEAR or prefix is None or sequence is None:
            continue
        if prefix in SPECIAL_PREFIXES:
            continue
        by_prefix[prefix][sequence] = (source, draw_date, name)

    gaps: list[tuple[str, int, tuple[str, date, str], tuple[str, date, str]]] = []
    for prefix, items in sorted(by_prefix.items()):
        sequences = sorted(items)
        for target in range(sequences[0] + 1, sequences[-1]):
            if target in items:
                continue
            lower_sequence = max(value for value in sequences if value < target)
            upper_sequence = min(value for value in sequences if value > target)
            gaps.append((prefix, target, items[lower_sequence], items[upper_sequence]))

    print("\nregular-family internal gaps:", len(gaps))
    if not gaps:
        print("Nothing to probe.")
        return 0

    connector = DomainRegistry().get_connector(DOMAIN)
    assert connector is not None

    found = []
    unresolved = []

    for prefix, target, lower, upper in gaps:
        lower_source, lower_date, lower_name = lower
        upper_source, upper_date, upper_name = upper
        lower_drawno = legacy_drawno(lower_source)
        upper_drawno = legacy_drawno(upper_source)

        print(f"\nGAP {prefix}-{target}")
        print("   lower neighbor:", lower_source, "|", lower_date.isoformat(), "|", lower_name)
        print("   upper neighbor:", upper_source, "|", upper_date.isoformat(), "|", upper_name)

        if lower_drawno is None or upper_drawno is None:
            print("   probe skipped: neighboring sources are not both legacy numeric addresses")
            unresolved.append((prefix, target, 0))
            continue

        candidates = bounded_candidates(lower_drawno, upper_drawno)
        print("   bounded candidate addresses:", len(candidates))

        inspected = 0
        match_row = None
        for drawno in candidates:
            source = f"legacy:{drawno}"
            if source in known:
                continue

            inspected += 1
            doc = connector.retrieve(source)
            if doc.error or not doc.content:
                continue

            parsed = connector.parse(bytes(doc.content)) or {}
            draw_date_text = str(parsed.get("draw_date") or "")
            name = normalize_name(parsed.get("lottery_name"))
            found_prefix, found_sequence = decode_code(name)
            if found_prefix != prefix or found_sequence != target:
                continue

            try:
                found_date = parse_draw_date(draw_date_text)
            except ValueError:
                continue

            match_row = (source, found_date, name)
            break

        print("   addresses actually inspected:", inspected)
        if match_row is None:
            print("   result: NOT FOUND within bounded neighborhood")
            unresolved.append((prefix, target, inspected))
            continue

        source, found_date, name = match_row
        print("   FOUND:", source, "|", found_date.isoformat(), "|", name)
        found.append((prefix, target, source, found_date, name, inspected))

    print("\n=== SEQUENCE-GAP PROBE SUMMARY ===")
    print("regular-family gaps tested:", len(gaps))
    print("verified missing results found:", len(found))
    for prefix, target, source, found_date, name, inspected in found:
        print(
            f"   {prefix}-{target} | {source} | {found_date.isoformat()} | "
            f"inspected={inspected} | {name}"
        )
    print("unresolved gaps:", len(unresolved))
    for prefix, target, inspected in unresolved:
        print(f"   {prefix}-{target} | inspected={inspected}")
    print("Memory changed: NO")
    print("source coverage proven: NO — this probe only resolves explicit sequence gaps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
