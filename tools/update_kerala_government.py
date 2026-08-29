from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path

from cossse.memory import Memory
from nokku.lottery.kerala.living import (
    DOMAIN,
    _discover_values,
    kerala_today,
    recall_kerala_facts,
    refresh_current_frontier,
)
from nokku.runtime import living_memory_path


# Living handoff boundary for the shared Banyan Government export.
EXPORT_START_DATE = date(2026, 8, 29)


def export_path() -> Path:
    """Return the application-neutral Banyan export path."""
    if Path("/workspaces").exists():
        return Path("/workspaces/.banyan/exports/kerala_lottery_government.json")
    return (
        Path.home()
        / ".local"
        / "share"
        / "banyan"
        / "exports"
        / "kerala_lottery_government.json"
    )


def export_records(*, anchor: date, memory_path: Path) -> list[dict[str, object]]:
    """Return latest preserved official draw reports for the shared-export epoch."""
    known: dict[str, dict[str, object]] = {}

    with Memory(memory_path) as memory:
        for value in _discover_values(memory):
            body = value.get("body", {})
            if body.get("experience") != "capability_attempt":
                continue
            if body.get("capability") != "collect":
                continue

            outcome = body.get("outcome") or {}
            request = outcome.get("request") or {}
            if request.get("domain_path") != DOMAIN:
                continue

            status = (outcome.get("execution") or {}).get("status")
            if status not in ("success", "partial"):
                continue

            source = str(request.get("source") or "")
            if not source:
                continue

            parsed = (outcome.get("data") or {}).get("parsed") or {}
            raw_date = str(parsed.get("draw_date") or "")
            try:
                draw_date = datetime.strptime(raw_date, "%d/%m/%Y").date()
            except ValueError:
                continue

            if draw_date < EXPORT_START_DATE or draw_date > anchor:
                continue

            # Receipt order is storage order; a later correction for one source wins.
            known[source] = {
                "source": source,
                "draw_date": raw_date,
                "lottery_name": parsed.get("lottery_name"),
                "parsed": parsed,
            }

    return sorted(
        known.values(),
        key=lambda item: (
            datetime.strptime(str(item["draw_date"]), "%d/%m/%Y").date(),
            str(item["source"]),
        ),
    )


def main() -> None:
    anchor = kerala_today()
    memory_path = living_memory_path()

    before = recall_kerala_facts(memory_path)
    before_latest = max(before, key=lambda item: item.draw_date) if before else None

    refreshed = refresh_current_frontier(
        anchor=anchor,
        facts=before,
        memory_path=memory_path,
    )

    after = recall_kerala_facts(memory_path)
    after_latest = max(after, key=lambda item: item.draw_date) if after else None

    records = export_records(anchor=anchor, memory_path=memory_path)
    target = export_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": 1,
        "domain_path": DOMAIN,
        "export_start_date": EXPORT_START_DATE.isoformat(),
        "cutoff_date": anchor.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_source": after_latest.source if after_latest is not None else None,
        "latest_draw_date": (
            after_latest.draw_date.isoformat() if after_latest is not None else None
        ),
        "record_count": len(records),
        "records": records,
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== KERALA GOVERNMENT DATA UPDATE ===")
    print("Update through:", anchor)
    print("Before:", before_latest)
    print("New sources:", refreshed or "NONE")
    print("After:", after_latest)
    print("Total verified facts:", len(after))
    print()
    print("=== BANYAN GOVERNMENT EXPORT ===")
    print("Export start:", EXPORT_START_DATE)
    print("Records exported:", len(records))
    print("Export file:", target)
    print("Export bytes:", target.stat().st_size)


if __name__ == "__main__":
    main()
