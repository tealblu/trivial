from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class PoopleScoreParser(ScoreParser):
    """Parser for a pasted poople.io share.

    Example score message (see ``example_message``): the puzzle number in the
    header ("Poople #423") is the iteration — everything is keyed off it, not
    the date the share was posted. The header's "X/Y" is guesses over par, the
    shortest possible path, so fewer guesses is better.
    """

    # A full pasted share — the header carries the iteration number.
    example_message = """Poople #423 6/5
⬜⬜⬜⬜
⬜🟫⬜⬜
🟫🟫⬜⬜
🟫🟫⬜⬜
🟫🟫⬜⬜
🟫🟫⬜🟫
🟫🟫🟫🟫

https://poople.io/"""

    game = "poople"
    score_sort = "asc"  # fewer guesses is better
    game_url = "https://poople.io"

    # "Poople #423 6/5" — puzzle number, guesses and par (shortest path).
    _header_re = re.compile(
        r"\bPoople\s*#?\s*(?P<number>\d+)\s+"
        r"(?P<guesses>\d+)\s*/\s*(?P<par>\d+)",
        re.IGNORECASE,
    )
    # one row is 4 tiles: brown (letter matches "poop") or blank
    _row_re = re.compile(r"[\U0001f7eb\u2b1c]{4}")

    def can_parse(self, message: discord.Message) -> bool:
        if self._header_re.search(message.content) is None:
            return False
        return bool(self._rows(message.content))

    def parse(self, message: discord.Message) -> ScoreResponse:
        header = self._header_re.search(message.content)
        number = header.group("number")
        guesses = header.group("guesses")
        par = header.group("par")
        rows = self._rows(message.content)

        resp = self._build_response(
            message,
            title="Poople",
            score=int(guesses),
            iteration=number,
        )
        resp.meta.update(
            number=number,
            guesses=guesses,
            par=par,
            grid="\n".join(rows),
        )
        resp.description = "\n".join(
            [f"Poople #{number} {guesses}/{par}", "", *rows]
        )
        return resp

    def _rows(self, content: str) -> list[str]:
        """Grid rows in the order they appear."""
        return self._row_re.findall(content)
