from __future__ import annotations

import re
from datetime import datetime

import discord

from .base import ScoreParser, ScoreResponse


class GundleScoreParser(ScoreParser):
    """Parser for a pasted Gundle share.

    Example score message (see ``example_message``): the header carries the
    game identifier, date, and score/total. The grid uses coloured squares:
    green 🟩 (correct position), yellow 🟨 (in wrong position), and ⬛ (not present).
    """

    # A full pasted share
    example_message = """GUNDLE Oct 12 — 2/6

🟩🟩🟩🟩🟩🟩🟩
🟩🟩🟨⬛⬛🟨⬛

Play at: https://playgundle.com/"""

    game = "gundle"
    score_sort = "asc"  # fewer guesses is better
    game_url = "https://playgundle.com/"

    # "GUNDLE Oct 12 — 2/6" — game identifier, date, and score/total,
    # separated by an em dash (—).
    _header_re = re.compile(
        r"\bGUNDLE\s+(?P<date>\w+\s+\d{1,2})\s*—\s*(?P<guesses>\d+)\s*/\s*(?P<total>\d+)",
        re.IGNORECASE,
    )
    # one row is 7 tiles: green 🟩, yellow 🟨, or blank ⬛
    _row_re = re.compile(r"[🟨🟩⬛]{7}")

    def can_parse(self, message: discord.Message) -> bool:
        content = message.content
        if self._header_re.search(content) is None:
            return False
        # Require at least one grid row so a bare header without tiles doesn't match.
        if not self._rows(content):
            return False
        # The share URL is optional — it can be stripped (e.g. to drop the
        # embed) and the header + grid still identify the game.
        return True

    def parse(self, message: discord.Message) -> ScoreResponse:
        header = self._header_re.search(message.content)
        date = header.group("date")
        guesses = header.group("guesses")
        total = header.group("total")

        # Convert date "Oct 12" to YYYY-MM-DD iteration
        try:
            parsed_date = datetime.strptime(date, "%b %d")
            # If year is 1900 (default from strptime), use current year
            if parsed_date.year == 1900:
                parsed_date = parsed_date.replace(year=datetime.now().year)
            iteration = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            iteration = date

        rows = self._rows(message.content)

        score = int(guesses) if guesses else None

        resp = self._build_response(
            message,
            title="Gundle",
            score=score,
            iteration=iteration,
        )
        resp.meta.update(
            date=date,
            guesses=guesses,
            total=total,
            grid="\n".join(rows),
        )
        resp.description = "\n".join(
            [f"Gundle {date} {guesses}/{total}", "", *rows]
        )
        return resp

    def _rows(self, content: str) -> list[str]:
        """Grid rows in the order they appear."""
        return self._row_re.findall(content)