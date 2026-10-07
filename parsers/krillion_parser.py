from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class KrillionScoreParser(ScoreParser):
    """Parser for Krillion daily scores.

    Example score message (see ``example_message``): the puzzle number in the
    header ("Krillion #64") is the iteration — everything is keyed off it, not
    the date the share was posted.
    """

    # A full pasted share — the header carries the iteration number.
    example_message = """Krillion #64

8700"""

    game = "krillion"
    score_sort = "desc"  # higher score is better
    game_url = "https://krillion.io"

    # Matches "Krillion #64" — the puzzle number.
    _header_re = re.compile(r"Krillion\s*#\s*(\d+)", re.IGNORECASE)

    def can_parse(self, message: discord.Message) -> bool:
        # Require the "Krillion #N" header and a standalone numeric score line.
        if self._header_re.search(message.content) is None:
            return False
        return any(line.strip().isdigit() for line in message.content.splitlines())

    def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        header_match = self._header_re.search(message.content)
        number = header_match.group(1) if header_match else ""

        score = None
        for line in lines:
            stripped = line.strip()
            if stripped.isdigit():
                score = int(stripped)
                break

        board_lines = [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().isdigit()
            and not self._header_re.search(line)
        ]

        resp = self._build_response(
            message, title="Krillion", score=score, iteration=number
        )
        if number:
            resp.meta["number"] = number

        header = f"Krillion #{number}" if number else "Krillion"
        resp.description = "\n".join([header, *board_lines])

        return resp
