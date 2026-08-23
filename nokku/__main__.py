"""Run Nokku's first living decision loop with ``python -m nokku``."""

from __future__ import annotations

import argparse
from datetime import date

from nokku.lottery.kerala.living import kerala_today, run_weekly_decision
from nokku.preferences import VALID_WEEK_STARTS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m nokku",
        description="Nokku — before you decide... Nokku.",
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="Should I buy a Kerala lottery this week?",
        help="Decision request in conversational form.",
    )
    parser.add_argument(
        "--date",
        dest="anchor_date",
        help="Decision date as YYYY-MM-DD. Defaults to the current Kerala date.",
    )
    parser.add_argument(
        "--week-start",
        choices=VALID_WEEK_STARTS,
        help="Override the saved decision-week start for this run.",
    )
    parser.add_argument(
        "--remember-week-start",
        action="store_true",
        help="Persist --week-start as the Kerala Lottery preference.",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Use durable Memory only; do not probe the current numeric frontier.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    anchor = date.fromisoformat(args.anchor_date) if args.anchor_date else kerala_today()

    result = run_weekly_decision(
        args.request,
        anchor=anchor,
        week_start_override=args.week_start,
        remember_week_start=args.remember_week_start,
        refresh=not args.no_refresh,
    )
    decision = result.decision

    print("\n=== NOKKU — KERALA LOTTERY WEEKLY DECISION ===")
    print("request:", args.request)
    print("decision date:", anchor.isoformat(), "(Kerala local date)")
    print("recommendation:", decision.recommendation)
    print("decision week:", decision.week_start.isoformat(), "->", decision.week_end.isoformat())
    print("week-start preference:", result.week_start_preference)

    if decision.recommendation == "BUY":
        print("preferred date:", decision.preferred_date.isoformat() if decision.preferred_date else "NONE")
        print("backup date:", decision.backup_date.isoformat() if decision.backup_date else "NONE")
    else:
        print(
            "participation date if you override SKIP:",
            decision.preferred_date.isoformat() if decision.preferred_date else "NONE",
        )
        print(
            "backup if you override SKIP:",
            decision.backup_date.isoformat() if decision.backup_date else "NONE",
        )

    print("timing:", decision.preferred_time)
    print("user override detected:", decision.override or "NONE")
    print("current sources refreshed:", ", ".join(result.refreshed_sources) or "NONE")
    print("\nevidence:")
    for item in decision.evidence_summary:
        print("  -", item)
    print("\nuncertainty:", decision.uncertainty)
    print("decision memory receipt:", result.memory_id)
    print("\nBefore you decide... Nokku.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
