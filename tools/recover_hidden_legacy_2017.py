from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime

from collector.collect import collect
from collector.domains.games.chance.lottery.kerala.legacy import LegacyAddressScanStalled
from collector.domains.registry import DomainRegistry
from cossse.adapters.collector import CollectorAdapter
from cossse.adapters.memory import MemoryAdapter
from cossse.flow import DispositionStatus, Flow, Meaning
from cossse.memory import Memory
from nokku.runtime import living_memory_path


DOMAIN = "games/chance/lottery/kerala"
YEAR = 2017
MEMORY_PATH = living_memory_path()
OLDER_EVIDENCE_TARGET = 8
MAX_CONSECUTIVE_UNUSABLE = 100
MAX_CONTINUATION_PROBE = 100
DRAW_CODE_RE = re.compile(
    r"\bLOTTERY\s+NO\.?\s*([A-Z]+-\d+)(?:ST|ND|RD|TH)?\s+DRAW\b"
)


def parse_draw_date(value: str) -> date:
    return datetime.strptime(value, "%d/%m/%Y").date()


def normalize_name(value: object) -> str:
    return " ".join(str(value or "").split())


def event_code(lottery_name: str) -> str:
    """Return the published draw code without confusing labels such as BUMPER-2017."""
    normalized = lottery_name.upper()
    match = DRAW_CODE_RE.search(normalized)
    return match.group(1) if match else normalized


def discover_known_draws(memory: Memory):
    flow = Flow()
    adapter = MemoryAdapter(memory)
    discovery = flow.encounter(
        Meaning(body={"need": "discover_preserved_experiences", "requester": "nokku"}),
        [adapter],
    )
    assert discovery.status == DispositionStatus.CLAIMED
    assert len(discovery.feedback) == 1

    receipts = discovery.feedback[0].body.get("receipts", [])
    known: dict[str, dict[str, object]] = {}

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


def preserve_experience(result_meaning: Meaning) -> str:
    with Memory(MEMORY_PATH) as memory:
        disposition = Flow().encounter(result_meaning, [MemoryAdapter(memory)])
    assert disposition.status == DispositionStatus.CLAIMED
    assert len(disposition.feedback) == 1
    return disposition.feedback[0].body["memory_id"]


def target_records(known: dict[str, dict[str, object]]):
    records: list[tuple[str, date, str]] = []
    for source, item in known.items():
        parsed = item["parsed"]
        draw_date_text = parsed.get("draw_date")
        if not draw_date_text or draw_date_text == "Unknown":
            continue
        try:
            draw_date = parse_draw_date(str(draw_date_text))
        except ValueError:
            continue
        if draw_date.year == YEAR:
            records.append((source, draw_date, normalize_name(parsed.get("lottery_name"))))
    return records


def visible_boundary(connector):
    families = connector.legacy_history_resolver.families()
    published_sources = {
        item.source
        for family in families
        for item in family.sources
    }

    rows = []
    for family in families:
        if not family.sources:
            continue
        item = family.sources[-1]
        doc = connector.retrieve(item.source)
        if doc.error or not doc.content:
            continue
        parsed = connector.parse(bytes(doc.content)) or {}
        draw_date_text = str(parsed.get("draw_date") or "")
        if not draw_date_text or draw_date_text == "Unknown":
            continue
        try:
            draw_date = parse_draw_date(draw_date_text)
        except ValueError:
            continue
        rows.append((draw_date, item.drawno, item.source, family.label or family.option))

    if not rows:
        raise RuntimeError("Could not establish the visible legacy boundary.")

    rows.sort()
    return rows[0], published_sources


def main() -> int:
    print("\n=== NOKKU LIVING HABITAT — HIDDEN LEGACY 2017 RECOVERY ===")
    print("preservation: YES, but only independently verified 2017 result facts")
    print("calendar no-draw classification: DISABLED until source coverage is proven")
    print("cross-year evidence target:", OLDER_EVIDENCE_TARGET, "verified 2016 records after January 2017 is observed")
    print("stall safety:", MAX_CONSECUTIVE_UNUSABLE, "consecutive unusable addresses")
    print("bounded continuation probe:", MAX_CONTINUATION_PROBE, "addresses after a real stall")

    assert MEMORY_PATH.exists(), f"Expected existing Memory at {MEMORY_PATH}"

    connector = DomainRegistry().get_connector(DOMAIN)
    assert connector is not None, f"Missing Collector connector for {DOMAIN}"
    address_scan = getattr(connector, "iter_legacy_address_records", None)
    continuation_resolver = getattr(connector, "resolve_legacy_address_continuation", None)
    if not callable(address_scan) or not callable(continuation_resolver):
        raise SystemExit(
            "Collector does not expose the hidden legacy scan + continuation capabilities. "
            "Use the Collector exp/kerala-hidden-legacy-address-scan branch."
        )

    with Memory(MEMORY_PATH) as memory:
        receipts_before, known_before = discover_known_draws(memory)

    existing_2017 = target_records(known_before)
    print("\n1. Nokku wakes")
    print("   memory:", MEMORY_PATH)
    print("   receipts discovered:", len(receipts_before))
    print("   existing 2017 records:", len(existing_2017))

    (boundary_date, boundary_drawno, boundary_source, boundary_family), published_sources = visible_boundary(connector)
    start_drawno = boundary_drawno - 1

    print("\n2. Visible index boundary")
    print("   family:", boundary_family)
    print("   source:", boundary_source)
    print("   held date:", boundary_date.isoformat())
    print("   hidden scan starts at:", f"legacy:{start_drawno}")

    collector_adapter = CollectorAdapter(collect)
    newly_preserved: list[tuple[str, date, str, str]] = []
    scanned_valid: list[tuple[str, date, str, bool]] = []
    older_evidence: list[tuple[str, date, str]] = []
    january_seen = False
    inspected = 0
    usable = 0
    stop_reason = "address space exhausted"
    unresolved_stall = False
    stalls_encountered = 0
    continuations_resolved = 0

    def progress(source: str, draw_date: datetime | None, is_usable: bool) -> None:
        nonlocal inspected, usable
        inspected += 1
        if is_usable:
            usable += 1
        if inspected <= 3 or inspected % 250 == 0:
            suffix = draw_date.date().isoformat() if draw_date else "unusable"
            print(f"   scan progress: {inspected} addresses | {usable} valid | latest {source} {suffix}")

    def handle_record(record) -> bool:
        nonlocal january_seen, stop_reason

        source = record.source
        indexed = source in published_sources
        scanned_valid.append((source, record.draw_date, record.lottery_name, indexed))

        if record.draw_date.year == YEAR:
            if record.draw_date.month == 1:
                january_seen = True

            if source in known_before:
                return False

            result_meaning = collect_source(collector_adapter, source)
            report = result_meaning.body["outcome"]
            status = report["execution"]["status"]
            if status not in ("success", "partial"):
                print("\n❌ HIDDEN LEGACY COLLECTION FAILURE")
                print("   source:", source)
                print("   status:", status)
                for event in report["execution"].get("events", []):
                    print("   event:", event)
                raise AssertionError("Stopped safely at the first unresolved collection result.")

            parsed = (report.get("data") or {}).get("parsed") or {}
            draw_date_text = parsed.get("draw_date")
            assert draw_date_text and draw_date_text != "Unknown"
            draw_date = parse_draw_date(str(draw_date_text))
            assert draw_date == record.draw_date

            lottery_name = normalize_name(parsed.get("lottery_name"))
            memory_id = preserve_experience(result_meaning)
            newly_preserved.append((source, draw_date, lottery_name, memory_id))
            known_before[source] = {"memory_id": memory_id, "parsed": parsed, "outcome": report}
            print(
                f"   RECOVERED {source} | {draw_date.isoformat()} | "
                f"{'INDEXED' if indexed else 'UNINDEXED'} | {lottery_name}"
            )
            return False

        if january_seen and record.draw_date.year < YEAR:
            older_evidence.append((source, record.draw_date, record.lottery_name))
            print(
                f"   OLDER-EVIDENCE {source} | {record.draw_date.isoformat()} | "
                f"{record.lottery_name}"
            )
            if len(older_evidence) >= OLDER_EVIDENCE_TARGET:
                stop_reason = (
                    f"cross-year evidence target reached ({OLDER_EVIDENCE_TARGET} verified pre-2017 records)"
                )
                return True

        return False

    print("\n3. Recovering hidden verified 2017 results...")
    current_start = start_drawno
    finished = False

    while current_start >= 1 and not finished:
        try:
            for record in address_scan(
                current_start,
                max_consecutive_unusable=MAX_CONSECUTIVE_UNUSABLE,
                progress=progress,
            ):
                if handle_record(record):
                    finished = True
                    break

            if finished:
                break

            stop_reason = "address space exhausted"
            break

        except LegacyAddressScanStalled as exc:
            stalls_encountered += 1
            print(
                f"   STALL {stalls_encountered}: legacy:{exc.last_drawno} after "
                f"{exc.consecutive_unusable} consecutive unusable addresses"
            )
            print(
                f"   asking Collector for a bounded continuation within "
                f"{MAX_CONTINUATION_PROBE} lower addresses..."
            )

            continuation = continuation_resolver(
                exc.last_drawno,
                max_probe=MAX_CONTINUATION_PROBE,
                progress=progress,
            )

            if continuation is None:
                unresolved_stall = True
                stop_reason = (
                    f"{exc} No verified continuation found within "
                    f"{MAX_CONTINUATION_PROBE} lower addresses."
                )
                break

            continuations_resolved += 1
            print(
                f"   CONTINUATION {continuations_resolved}: {continuation.source} | "
                f"{continuation.draw_date.isoformat()} | {continuation.lottery_name}"
            )

            if handle_record(continuation):
                finished = True
                break

            current_start = continuation.drawno - 1

    print("\n4. Restarting Nokku/Memory...")
    with Memory(MEMORY_PATH) as memory:
        receipts_after, known_after = discover_known_draws(memory)

    target_after = target_records(known_after)
    known_after_sources = {source for source, _draw_date, _name in target_after}
    missing_preserved = [source for source, *_rest in newly_preserved if source not in known_after_sources]
    assert not missing_preserved, f"Restart recall missing recovered sources: {missing_preserved[:10]}"

    by_identity: dict[tuple[date, str], list[str]] = defaultdict(list)
    for source, draw_date, name in target_after:
        by_identity[(draw_date, event_code(name))].append(source)
    duplicate_events = {
        identity: sources
        for identity, sources in by_identity.items()
        if len(set(sources)) > 1
    }
    assert not duplicate_events, f"Exact event duplication appeared: {duplicate_events}"

    month_counts = Counter(draw_date.strftime("%Y-%m") for _, draw_date, _ in target_after)
    unindexed_2017_seen = [item for item in scanned_valid if item[1].year == YEAR and not item[3]]
    scan_dates = [item[1] for item in scanned_valid]

    print("\n=== 2017 HIDDEN RECOVERY CHECKPOINT ===")
    print("addresses inspected:", inspected)
    print("valid legacy records encountered:", len(scanned_valid))
    if scan_dates:
        print("observed valid date span:", min(scan_dates).isoformat(), "->", max(scan_dates).isoformat())
    print("unindexed 2017 records encountered:", len(unindexed_2017_seen))
    print("newly preserved 2017 records:", len(newly_preserved))
    print("verified pre-2017 evidence after January seen:", len(older_evidence))
    print("scan stalls encountered:", stalls_encountered)
    print("bounded continuations resolved:", continuations_resolved)
    print("stop reason:", stop_reason)
    print("source coverage status:", "UNRESOLVED — address-order chronology is not assumed")
    print("calendar no-draw classification:", "NOT PERFORMED")
    print("unresolved final stall:", "YES" if unresolved_stall else "NO")

    print("\n2017 month counts currently in Memory")
    for month_number in range(1, 13):
        month = f"{YEAR}-{month_number:02d}"
        print(f"   {month}: {month_counts.get(month, 0)}")
    print("total 2017 records currently in Memory:", len(target_after))
    print("exact cross-source event duplicates:", len(duplicate_events))
    print("receipts before:", len(receipts_before))
    print("receipts after:", len(receipts_after))
    print("restart recall of newly preserved records: YES")

    print("\n✅ RECOVERY CHECKPOINT COMPLETE — facts preserved; completeness not yet claimed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
