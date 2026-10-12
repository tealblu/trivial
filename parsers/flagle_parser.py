from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class FlagleScoreParser(ScoreParser):
    """Parser for a pasted Flagle share.

    Example score message (see ``example_message``): the puzzle number in
    the header ("Flagle #1672") is the iteration — everything is keyed
    off it, not the date the share was posted.
    """

    # A full pasted share
    example_message = """Flagle #1672 - 4/6 🏁

🟨⬛⬛⬛⬛
🟩🟩🟨⬛⬛
🟩🟩🟩🟨⬛
🟩🟩🟩🟩🟩

https://flagle-game.com/"""

    game = "flagle"
    score_sort = "asc"  # fewer guesses is better
    game_url = "https://flagle-game.com/"

    # "Flagle #1672 - 4/6" or "Flagle #1,672 - X/6" — the dash is part
    # of Flagle's share header, so casual mentions don't match.
    _header_re = re.compile(
        r"\bFlagle\s*#\s*(?P<number>\d{1,5}(?:,\d{3})*)\s*-\s*"
        r"(?P<guesses>\d+|[xX])\s*/\s*(?P<total>\d+)",
        re.IGNORECASE,
    )
    # one row is 5+ tiles: green, yellow, or blank (⬛ = not in the flag)
    _row_re = re.compile(r"[\U0001f7e8\U0001f7e9\u2b1b\u2b1c]+")

    def can_parse(self, message: discord.Message) -> bool:
        if self._header_re.search(message.content) is None:
            return False
        return bool(self._rows(message.content))

    def parse(self, message: discord.Message) -> ScoreResponse:
        header = self._header_re.search(message.content)
        number = header.group("number")
        guesses = header.group("guesses").upper()
        total = header.group("total")
        rows = self._rows(message.content)

        # get score from header
        score = int(total) if guesses == "X" else int(guesses)

        resp = self._build_response(
            message,
            title="Flagle",
            score=score,
            iteration=number.replace(",", ""),
        )
        resp.meta.update(
            number=number.replace(",", ""),
            guesses=guesses,
            total=total,
            grid="\n".join(rows),
        )
        resp.description = "\n".join(
            [f"Flagle #{number} - {guesses}/{total} 🏁", "", *rows]
        )
        return resp

    def _rows(self, content: str) -> list[str]:
        """Grid rows in the order they appear."""
        return self._row_re.findall(content)
