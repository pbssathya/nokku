from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
YEAR = 2017
MEMORY_PATH = living_memory_path()
CODE_RE = re.compile(r"\b([A-Z]+)-(\d+)\b")


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

        known[source] = {
            "parsed": (outcome.get("data") or {}).get("parsed") or {},
            "memory_id": receipt["memory_id"],
        }

    return known


def decoded_records(known: dict[str, dict[str, object]]):
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
        match = CODE_RE.search(name.upper())
        prefix = match.group(1) if match else None
        sequence = int(match.group(2)) if match else None
        records.append((source, draw_date, name, prefix, sequence))
    return records


def sequence_summary(records, year: int):
    by_prefix: dict[str, list[tuple[int, date, str, str]]] = defaultdict(list)
    unparsed = []

    for source, draw_date, name, prefix, sequence in records:
        if draw_date.year != year:
            continue
        if prefix is None or sequence is None:
            unparsed.append((source, draw_date, name))
            continue
        by_prefix[prefix].append((sequence, draw_date, source, name))

    return by_prefix, unparsed


def main() -> int:
    print("=== NOKKU READ-ONLY 2017 SEQUENCE CONTINUITY AUDIT ===")
    print("preservation: NO")
    print("network retrieval: NO")
    print("purpose: inspect remembered event-sequence continuity before any completeness claim")
    print("calendar no-draw classification: NOT PERFORMED")

    assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"
    with Memory(MEMORY_PATH) as memory:
        known = discover_known(memory)

    records = decoded_records(known)
    target = [item for item in records if item[1].year == YEAR]
    previous = [item for item in records if item[1].year == YEAR - 1]
    following = [item for item in records if item[1].year == YEAR + 1]

    print("\n1. Remembered facts")
    print("   total known Kerala sources:", len(known))
    print("   2016 records in Memory:", len(previous))
    print("   2017 records in Memory:", len(target))
    print("   2018 records in Memory:", len(following))

    target_groups, target_unparsed = sequence_summary(records, YEAR)
    previous_groups, _ = sequence_summary(records, YEAR - 1)
    following_groups, _ = sequence_summary(records, YEAR + 1)

    print("\n2. 2017 published-code sequence audit")
    all_internal_contiguous = True

    for prefix in sorted(target_groups):
        items = target_groups[prefix]
        by_sequence: dict[int, list[tuple[date, str, str]]] = defaultdict(list)
        for sequence, draw_date, source, name in items:
            by_sequence[sequence].append((draw_date, source, name))

        sequences = sorted(by_sequence)
        minimum = sequences[0]
        maximum = sequences[-1]
        missing = [value for value in range(minimum, maximum + 1) if value not in by_sequence]
        duplicate_sequences = {
            value: entries for value, entries in by_sequence.items() if len(entries) > 1
        }
        dates = [entry[0] for entries in by_sequence.values() for entry in entries]
        contiguous = not missing and not duplicate_sequences
        all_internal_contiguous = all_internal_contiguous and contiguous

        print(
            f"   {prefix}: records={len(items)} | sequence={minimum}->{maximum} | "
            f"missing={len(missing)} | duplicate-sequence={len(duplicate_sequences)} | "
            f"dates={min(dates).isoformat()}->{max(dates).isoformat()} | "
            f"internal-continuity={'YES' if contiguous else 'NO'}"
        )
        if missing:
            print("      missing sequence values:", ", ".join(map(str, missing[:30])))
            if len(missing) > 30:
                print("      ...", len(missing) - 30, "more")
        if duplicate_sequences:
            print("      duplicate sequence values:", ", ".join(map(str, sorted(duplicate_sequences))))

    if target_unparsed:
        print("\n   2017 records without a PREFIX-N sequence code:", len(target_unparsed))
        for source, draw_date, name in target_unparsed[:20]:
            print("      ", source, "|", draw_date.isoformat(), "|", name)
        if len(target_unparsed) > 20:
            print("      ...", len(target_unparsed) - 20, "more")

    print("\n3. Remembered year-boundary sequence checks")
    boundary_rows = 0
    lower_matches = 0
    upper_matches = 0

    for prefix in sorted(target_groups):
        target_sequences = sorted(item[0] for item in target_groups[prefix])
        target_min = min(target_sequences)
        target_max = max(target_sequences)

        previous_sequences = sorted(item[0] for item in previous_groups.get(prefix, []))
        following_sequences = sorted(item[0] for item in following_groups.get(prefix, []))

        lower = "NO 2016 MEMORY"
        if previous_sequences:
            previous_max = max(previous_sequences)
            lower = f"2016 max={previous_max} | expected={target_min - 1} | match={'YES' if previous_max == target_min - 1 else 'NO'}"
            lower_matches += int(previous_max == target_min - 1)

        upper = "NO 2018 MEMORY"
        if following_sequences:
            following_min = min(following_sequences)
            upper = f"2018 min={following_min} | expected={target_max + 1} | match={'YES' if following_min == target_max + 1 else 'NO'}"
            upper_matches += int(following_min == target_max + 1)

        boundary_rows += 1
        print(f"   {prefix}: lower [{lower}] | upper [{upper}]")

    print("\n4. Calendar observation from currently remembered 2017 facts")
    by_date: dict[date, list[tuple[str, str]]] = defaultdict(list)
    for source, draw_date, name, _prefix, _sequence in target:
        by_date[draw_date].append((source, name))

    all_days = []
    cursor = date(YEAR, 1, 1)
    end = date(YEAR, 12, 31)
    while cursor <= end:
        all_days.append(cursor)
        cursor += timedelta(days=1)

    zero_record_dates = [day for day in all_days if day not in by_date]
    multiple_record_dates = {day: values for day, values in by_date.items() if len(values) > 1}
    extra_records = sum(len(values) - 1 for values in multiple_record_dates.values())

    month_counts = Counter(draw_date.strftime("%Y-%m") for _, draw_date, *_ in target)
    for month in range(1, 13):
        key = f"{YEAR}-{month:02d}"
        print(f"   {key}: {month_counts.get(key, 0)}")

    print("   dates with zero remembered records:", len(zero_record_dates))
    print("   dates with multiple remembered records:", len(multiple_record_dates))
    print("   extra records on multiple-record dates:", extra_records)
    print("   calendar identity check:", len(all_days) - len(zero_record_dates) + extra_records, "records")

    if zero_record_dates:
        print("   zero-record dates (observation only):")
        for day in zero_record_dates:
            print("      ", day.isoformat())

    if multiple_record_dates:
        print("   multiple-record dates:")
        for day in sorted(multiple_record_dates):
            print("      ", day.isoformat())
            for source, name in multiple_record_dates[day]:
                print("         ", source, "|", name)

    print("\n=== SEQUENCE AUDIT SUMMARY ===")
    print("2017 records:", len(target))
    print("published-code families:", len(target_groups))
    print("unparsed-code records:", len(target_unparsed))
    print("all 2017 family sequences internally contiguous:", "YES" if all_internal_contiguous else "NO")
    print("families with remembered 2016 exact predecessor:", f"{lower_matches}/{boundary_rows}")
    print("families with remembered 2018 exact successor:", f"{upper_matches}/{boundary_rows}")
    print("source coverage proven:", "NO — this audit only tests remembered sequence structure")
    print("calendar no-draw classification performed:", "NO")
    print("No Collector result or Memory state was changed by this audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
