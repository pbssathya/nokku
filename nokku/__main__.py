"""Run Nokku's first living decision loop with ``python -m nokku``."""

from __future__ import annotations

import argparse
from datetime import date, datetime

from nokku.lottery.kerala.living import MissingUserTimezoneError, run_weekly_decision
from nokku.preferences import VALID_WEEK_STARTS


def parse_aware_datetime(value: str) -> datetime:
    """Parse an explicit ISO 8601 instant without guessing a timezone."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Astrology target must be an ISO 8601 datetime.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Astrology target instant must be timezone-aware.")
    return parsed


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
        help="Explicit decision date as YYYY-MM-DD. Otherwise Nokku uses the user's local date.",
    )
    parser.add_argument(
        "--timezone",
        dest="user_timezone",
        help="IANA user timezone, for example Asia/Kolkata or Europe/London.",
    )
    parser.add_argument(
        "--remember-timezone",
        action="store_true",
        help="Persist --timezone as the global user timezone.",
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
        "--astrology-at",
        dest="astrology_at",
        help=(
            "Optional timezone-aware ISO 8601 instant for the experimental astrology "
            "observation, for example 2026-08-28T12:00:00+05:30."
        ),
    )
    parser.add_argument(
        "--natal-moon-longitude",
        type=float,
        help=(
            "Explicit derived sidereal natal Moon longitude in degrees for the astrology "
            "observation. Nokku does not hardcode or infer this value."
        ),
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Use durable Memory only; do not refresh current result or schedule sources.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    anchor = date.fromisoformat(args.anchor_date) if args.anchor_date else None

    try:
        astrology_target_at = (
            parse_aware_datetime(args.astrology_at) if args.astrology_at else None
        )
        if args.natal_moon_longitude is not None and astrology_target_at is None:
            raise ValueError("--natal-moon-longitude requires --astrology-at.")

        result = run_weekly_decision(
            args.request,
            anchor=anchor,
            timezone_override=args.user_timezone,
            remember_timezone=args.remember_timezone,
            week_start_override=args.week_start,
            remember_week_start=args.remember_week_start,
            refresh=not args.no_refresh,
            astrology_target_at=astrology_target_at,
            astrology_natal_moon_longitude=args.natal_moon_longitude,
        )
    except MissingUserTimezoneError:
        print("Nokku needs your local timezone before it can interpret 'today' or 'this week'.")
        print(
            "Run again with, for example: "
            "--timezone Asia/Kolkata --remember-timezone"
        )
        return 2
    except ValueError as exc:
        print("Nokku could not use that setting:", exc)
        return 2

    decision = result.decision

    print("\n=== NOKKU — KERALA LOTTERY WEEKLY DECISION ===")
    print("request:", args.request)
    if result.user_timezone:
        print(
            "decision date:",
            result.decision_date.isoformat(),
            f"(user local date; timezone: {result.user_timezone})",
        )
    else:
        print("decision date:", result.decision_date.isoformat(), "(explicit date)")
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

    if result.frontier_refresh is not None:
        frontier = result.frontier_refresh
        print("\nfrontier refresh:", frontier.status.upper())
        print("  attempted sources:", ", ".join(frontier.attempted_sources) or "NONE")
        print("  refreshed sources:", ", ".join(frontier.refreshed_sources) or "NONE")
        print("  stop reason:", frontier.stop_reason)
        if frontier.failures:
            print("  failures:", "; ".join(frontier.failures))
        if frontier.uncertainty:
            print("  uncertainty:", "; ".join(frontier.uncertainty))

    fact_recall = result.fact_recall
    print("\nKerala fact recall:", fact_recall.status.upper())
    print("  facts:", len(fact_recall.facts))
    print("  examined values:", fact_recall.examined_values)
    print("  matching collection values:", fact_recall.matching_collection_values)
    print("  usable matching values:", fact_recall.usable_matching_values)
    print("  memory discovery:", fact_recall.memory_discovery.status.upper())
    if fact_recall.failures:
        print("  failures:", "; ".join(fact_recall.failures))
    if fact_recall.uncertainty:
        print("  uncertainty:", "; ".join(fact_recall.uncertainty))

    if result.schedule_collection is not None:
        schedule = result.schedule_collection
        print("\nschedule collection:", schedule.status.upper())
        print("  dates:", len(schedule.dates))
        print("  disposition:", schedule.disposition_status)
        print("  execution:", schedule.execution_status or "NONE")
        if schedule.failures:
            print("  failures:", "; ".join(schedule.failures))
        if schedule.uncertainty:
            print("  uncertainty:", "; ".join(schedule.uncertainty))

    if result.scheduled_draw_dates:
        print(
            "official upcoming draw dates:",
            ", ".join(item.isoformat() for item in result.scheduled_draw_dates),
        )
    elif not args.no_refresh:
        print("official upcoming draw dates: NONE AVAILABLE")

    if result.numerology_signals:
        print("\nnumerology observations (selection signals, not win probabilities):")
        for signal in result.numerology_signals:
            family = "yes" if signal.personal_day_in_369_family else "no"
            draw = ""
            if signal.draw_number is not None:
                draw = f"; draw {signal.draw_number} -> {signal.draw_reduction}"
            print(
                "  -",
                signal.target_date.isoformat(),
                f"personal day {signal.personal_day};",
                f"birth {signal.birth_number};",
                f"life path {signal.life_path};",
                f"personal year {signal.personal_year};",
                f"3/6/9 family: {family}{draw}",
            )

    if result.astrology_observation is not None:
        astrology = result.astrology_observation
        print("\nastrology observation (experimental methodology; not a win probability):")
        if astrology_target_at is not None:
            print("  target instant:", astrology_target_at.isoformat())
        print("  natal nakshatra:", astrology.natal_nakshatra)
        print("  natal lord:", astrology.natal_nakshatra_lord)
        print("  mahadasha:", astrology.mahadasha)
        print("  antardasha:", astrology.antardasha)
        print("  status:", astrology.status)
    elif result.astrology_observation_result is not None:
        receipt = result.astrology_observation_result
        print("\nastrology observation:", receipt.status.upper())
        if receipt.failures:
            print("  failures:", "; ".join(receipt.failures))
        if receipt.uncertainty:
            print("  uncertainty:", "; ".join(receipt.uncertainty))

    print("\nevidence:")
    for item in decision.evidence_summary:
        print("  -", item)
    print("\nuncertainty:", decision.uncertainty)

    preservation = result.decision_preservation
    print("\ndecision memory preservation:", preservation.status.upper())
    print("  memory id:", preservation.memory_id or "NONE")
    if preservation.failures:
        print("  failures:", "; ".join(preservation.failures))
    if preservation.uncertainty:
        print("  uncertainty:", "; ".join(preservation.uncertainty))

    print("\nBefore you decide... Nokku.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
