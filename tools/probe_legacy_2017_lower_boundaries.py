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
MAX_LOWER_PROBE = 500
REGULAR_PREFIXES = {"AK", "BN", "KN", "KR", "NR", "RN", "SS", "W"}
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
    return match.group(1).upper(), int(match.group(2))


def legacy_drawno(source: str):
    if not source.startswith("legacy:"):
        return None
    raw = source.split(":", 1)[1]
    return int(raw) if raw.isdigit() else None


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
        if source:
            known[source] = (outcome.get("data") or {}).get("parsed") or {}

    return known


def decoded_known_rows(known):
    rows = []
    for source, parsed in known.items():
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

        name = normalize_name(parsed.get("lottery_name"))
        prefix, sequence = decode_code(name)
        if prefix is None or sequence is None:
            continue
        rows.append((prefix, sequence, draw_date, drawno, source, name))
    return rows


def main() -> int:
    print("=== NOKKU READ-ONLY 2017 LOWER-BOUNDARY PROBE ===")
    print("preservation: NO")
    print("purpose: verify the exact pre-2017 predecessor for each regular 2017 lottery family")
    print("special family excluded:", "BR")
    print("maximum lower addresses inspected per family:", MAX_LOWER_PROBE)

    assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"
    with Memory(MEMORY_PATH) as memory:
        known = discover_known(memory)

    rows = decoded_known_rows(known)
    by_prefix: dict[str, list[tuple[int, date, int, str, str]]] = defaultdict(list)
    for prefix, sequence, draw_date, drawno, source, name in rows:
        if prefix in REGULAR_PREFIXES:
            by_prefix[prefix].append((sequence, draw_date, drawno, source, name))

    connector = DomainRegistry().get_connector(DOMAIN)
    assert connector is not None

    proven = []
    unresolved = []
    monotonic_failures = []

    for prefix in sorted(REGULAR_PREFIXES):
        family_rows = sorted(by_prefix.get(prefix, []), key=lambda item: item[0])
        target_rows = [row for row in family_rows if row[1].year == YEAR]
        if not target_rows:
            unresolved.append((prefix, "no remembered 2017 rows", 0))
            continue

        # Family-local drawno monotonicity is checked over all remembered rows for
        # this published code family. The lower-address probe is only interpreted
        # as predecessor evidence when that family-local ordering is clean.
        inversions = []
        for left, right in zip(family_rows, family_rows[1:]):
            if right[0] <= left[0]:
                continue
            if right[2] <= left[2]:
                inversions.append((left, right))

        first_2017 = min(target_rows, key=lambda item: item[0])
        first_sequence, first_date, anchor_drawno, anchor_source, first_name = first_2017
        target_sequence = first_sequence - 1

        print(f"\nFAMILY {prefix}")
        print(
            "   first remembered 2017 row:",
            f"{prefix}-{first_sequence}",
            "|",
            first_date.isoformat(),
            "|",
            anchor_source,
            "|",
            first_name,
        )
        print("   expected exact predecessor:", f"{prefix}-{target_sequence}")
        print("   remembered family-local address inversions:", len(inversions))

        if inversions:
            print("   result: NOT PROBED — family-local source order is not monotonic")
            monotonic_failures.append(prefix)
            unresolved.append((prefix, "family-local address inversion", 0))
            continue

        inspected_live = 0
        examined_total = 0
        found = None

        for drawno in range(anchor_drawno - 1, max(0, anchor_drawno - MAX_LOWER_PROBE - 1), -1):
            examined_total += 1
            source = f"legacy:{drawno}"

            parsed = known.get(source)
            if parsed is None:
                inspected_live += 1
                doc = connector.retrieve(source)
                if doc.error or not doc.content:
                    continue
                parsed = connector.parse(bytes(doc.content)) or {}

            name = normalize_name(parsed.get("lottery_name"))
            found_prefix, found_sequence = decode_code(name)
            if (found_prefix, found_sequence) != (prefix, target_sequence):
                continue

            draw_date_text = str(parsed.get("draw_date") or "")
            try:
                found_date = parse_draw_date(draw_date_text)
            except ValueError:
                continue

            found = (source, found_date, name)
            break

        print("   lower addresses examined:", examined_total)
        print("   live addresses fetched:", inspected_live)

        if found is None:
            print("   result: exact predecessor NOT FOUND within bounded lower window")
            unresolved.append((prefix, f"{prefix}-{target_sequence} not found", examined_total))
            continue

        source, found_date, name = found
        print("   FOUND:", source, "|", found_date.isoformat(), "|", name)
        boundary_ok = found_date.year < YEAR
        print("   predecessor is pre-2017:", "YES" if boundary_ok else "NO")
        if not boundary_ok:
            unresolved.append((prefix, f"predecessor falls in {found_date.year}", examined_total))
            continue

        proven.append((prefix, target_sequence, source, found_date, name, examined_total))

    print("\n=== 2017 LOWER-BOUNDARY PROBE SUMMARY ===")
    print("regular families tested:", len(REGULAR_PREFIXES))
    print("family-local monotonicity failures:", len(monotonic_failures))
    if monotonic_failures:
        print("   ", ", ".join(sorted(monotonic_failures)))
    print("exact pre-2017 predecessors verified:", len(proven))
    for prefix, sequence, source, found_date, name, examined in proven:
        print(
            f"   {prefix}-{sequence} | {source} | {found_date.isoformat()} | "
            f"examined={examined} | {name}"
        )
    print("unresolved regular-family lower boundaries:", len(unresolved))
    for prefix, reason, examined in unresolved:
        print(f"   {prefix} | examined={examined} | {reason}")
    print("Memory changed: NO")
    print(
        "2017 lower-boundary proof:",
        "YES" if len(proven) == len(REGULAR_PREFIXES) and not unresolved else "NO",
    )
    print("whole-year source coverage proven: NO — this probe tests only regular-family lower boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
