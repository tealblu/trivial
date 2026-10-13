from __future__ import annotations

import re
from datetime import datetime

import discord

from .base import ScoreParser, ScoreResponse


class AirportGuessrScoreParser(ScoreParser):
    """Parser for a pasted AirportGuessr share.

    Example score message (see ``example_message``): the share is keyed off
    the date it was posted, not a puzzle number. The iteration is therefore
    the message's date (``YYYY-MM-DD``).
    """

    # A full pasted share — the "I got the airport in X guesses today:" format,
    # followed by 3-tile grid rows using 🟥 (red) and 🟩 (green) emoji, and
    # ending with the game URL.
    example_message = """I got the airport in 3 guesses today:
🟥🟥🟩
https://planespottle.net/airportguessr"""

    game = "airportguessr"
    score_sort = "asc"  # fewer guesses is better
    game_url = "https://planespottle.net/airportguessr"

    # "I got the airport in X guesses today:" — no puzzle number; the share
    # date is the iteration.
    _header_re = re.compile(
        r"I\s+got\s+the\s+airport\s+in\s+(?P<guesses>\d+)\s+guess(?:es)?\s+today:",
        re.IGNORECASE,
    )
    # Rows of 🟥 (red) and 🟩 (green) emoji — the grid can have varying
    # numbers of tiles per row, so we match 1 or more tiles per line.
    _row_re = re.compile(r"[🟨🟩⬛🟥]+")

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
        guesses = int(header.group("guesses"))

        # Key the score off the message's date, not a puzzle number.
        # The day the score was logged is already set by
        # ``ScoreResponse.day`` (default ``today_str``), but we also set
        # ``iteration`` to ``YYYY-MM-DD`` so the board stays consistent.
        iteration = datetime.utcnow().strftime("%Y-%m-%d")

        resp = self._build_response(
            message,
            title="AirportGuessr",
            score=guesses,
            iteration=iteration,
        )
        resp.meta.update(
            grid="\n".join(self._rows(message.content)),
        )
        resp.description = "\n".join(
            [f"AirportGuessr in {guesses} guesses!", "", *resp.meta["grid"].splitlines()]
        )
        return resp

    def _rows(self, content: str) -> list[str]:
        """Grid rows in the order they appear."""
        return self._row_re.findall(content)