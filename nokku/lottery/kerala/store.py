"""Nokku-owned factual store for the Kerala Lottery living use case.

This is intentionally application-specific. It exists only because the living
use case needs to know which official draws it already owns and which serials
are missing. It is not a generalized COSsse store.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True, slots=True)
class DrawRecord:
    """Minimal draw identity Nokku currently needs to own."""

    draw_serial: int
    draw_date: str | None = None
    lottery_code: str | None = None
    lottery_name: str | None = None
    source_url: str | None = None


class KeralaLotteryStore:
    """Small SQLite store for known Kerala lottery draw identities."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS draws (
                    draw_serial INTEGER PRIMARY KEY,
                    draw_date TEXT,
                    lottery_code TEXT,
                    lottery_name TEXT,
                    source_url TEXT
                )
                """
            )

    def upsert_draw(self, draw: DrawRecord) -> None:
        """Insert or refresh one draw identity without creating duplicates."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO draws (
                    draw_serial, draw_date, lottery_code, lottery_name, source_url
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(draw_serial) DO UPDATE SET
                    draw_date = excluded.draw_date,
                    lottery_code = excluded.lottery_code,
                    lottery_name = excluded.lottery_name,
                    source_url = excluded.source_url
                """,
                (
                    draw.draw_serial,
                    draw.draw_date,
                    draw.lottery_code,
                    draw.lottery_name,
                    draw.source_url,
                ),
            )

    def known_serials(self) -> tuple[int, ...]:
        """Return known draw serials in ascending order."""

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT draw_serial FROM draws ORDER BY draw_serial"
            ).fetchall()
        return tuple(int(row[0]) for row in rows)

    def missing_serials(self) -> tuple[int, ...]:
        """Return internal gaps between the smallest and largest known serial."""

        known = self.known_serials()
        if len(known) < 2:
            return ()
        present = set(known)
        return tuple(
            serial
            for serial in range(known[0], known[-1] + 1)
            if serial not in present
        )

    def latest_serial(self) -> int | None:
        """Return the highest verified draw serial Nokku currently owns."""

        with self._connect() as connection:
            row = connection.execute("SELECT MAX(draw_serial) FROM draws").fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])

    def next_expected_serial(self) -> int | None:
        """Return the next sequential serial after the current highest draw."""

        latest = self.latest_serial()
        if latest is None:
            return None
        return latest + 1
