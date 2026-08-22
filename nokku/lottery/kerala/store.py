"""Nokku-owned factual store for the Kerala Lottery living use case.

This is intentionally application-specific. It exists only because the living
use case needs to know which official draws it already owns and which serials
are missing. It is not a generalized COSsse store.

For the initial ``testrun`` this store is deliberately database-less: a small
JSON document on disk is enough to prove the living behaviour. A database can
be introduced later only if real usage provides evidence that it is needed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DrawRecord:
    """Minimal draw identity Nokku currently needs to own."""

    draw_serial: int
    draw_date: str | None = None
    lottery_code: str | None = None
    lottery_name: str | None = None
    source_url: str | None = None


class KeralaLotteryStore:
    """Small file-backed store for known Kerala lottery draw identities."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, object]]:
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Kerala lottery store must contain a JSON list.")
        return data

    def _write(self, rows: list[dict[str, object]]) -> None:
        ordered = sorted(rows, key=lambda row: int(row["draw_serial"]))
        self.path.write_text(
            json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def upsert_draw(self, draw: DrawRecord) -> None:
        """Insert or refresh one draw identity without creating duplicates."""

        rows = self._read()
        replacement = asdict(draw)

        for index, row in enumerate(rows):
            if int(row["draw_serial"]) == draw.draw_serial:
                rows[index] = replacement
                break
        else:
            rows.append(replacement)

        self._write(rows)

    def known_serials(self) -> tuple[int, ...]:
        """Return known draw serials in ascending order."""

        return tuple(sorted(int(row["draw_serial"]) for row in self._read()))

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

        known = self.known_serials()
        return known[-1] if known else None

    def next_expected_serial(self) -> int | None:
        """Return the next sequential serial after the current highest draw."""

        latest = self.latest_serial()
        if latest is None:
            return None
        return latest + 1
