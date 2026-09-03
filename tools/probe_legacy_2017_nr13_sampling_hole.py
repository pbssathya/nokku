from __future__ import annotations

import re
from datetime import datetime

from collector.domains.registry import DomainRegistry


DOMAIN = "games/chance/lottery/kerala"
TARGET_PREFIX = "NR"
TARGET_SEQUENCE = 13
START_DRAWNO = 55223
END_DRAWNO = 55089
CODE_RE = re.compile(
    r"LOTTERY\s+NO\.\s*([A-Z]+)-(\d+)(?:ST|ND|RD|TH)?\b",
    flags=re.I,
)


def normalize_name(value: object) -> str:
    return " ".join(str(value or "").split())


def decode_code(name: str):
    match = CODE_RE.search(name.upper())
    if not match:
        return None, None
    return match.group(1), int(match.group(2))


def main() -> int:
    print("=== NOKKU READ-ONLY NR-13 SAMPLING-HOLE PROBE ===")
    print("preservation: NO")
    print("purpose: inspect the 135-address core interval omitted by the previous bounded candidate ordering")
    print("target: NR-13")
    print("address interval:", f"legacy:{START_DRAWNO} -> legacy:{END_DRAWNO}")

    connector = DomainRegistry().get_connector(DOMAIN)
    assert connector is not None

    inspected = 0
    usable = 0
    found = None

    for drawno in range(START_DRAWNO, END_DRAWNO - 1, -1):
        inspected += 1
        source = f"legacy:{drawno}"
        doc = connector.retrieve(source)
        if doc.error or not doc.content:
            continue

        parsed = connector.parse(bytes(doc.content)) or {}
        draw_date_text = str(parsed.get("draw_date") or "")
        name = normalize_name(parsed.get("lottery_name"))
        prefix, sequence = decode_code(name)
        if not draw_date_text or draw_date_text == "Unknown" or not name:
            continue

        try:
            draw_date = datetime.strptime(draw_date_text, "%d/%m/%Y").date()
        except ValueError:
            continue

        usable += 1
        print(f"   VALID {source} | {draw_date.isoformat()} | {name}")

        if prefix == TARGET_PREFIX and sequence == TARGET_SEQUENCE:
            found = (source, draw_date, name)
            break

    print("\n=== NR-13 SAMPLING-HOLE PROBE SUMMARY ===")
    print("addresses inspected:", inspected)
    print("usable official records encountered:", usable)
    if found:
        source, draw_date, name = found
        print("FOUND:", source, "|", draw_date.isoformat(), "|", name)
    else:
        print("result: NR-13 NOT FOUND in the previously omitted interval")
    print("Memory changed: NO")
    print("source coverage proven: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
