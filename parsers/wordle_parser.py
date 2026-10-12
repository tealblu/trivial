from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class WordleScoreParser(ScoreParser):
    """Parser for a pasted Wordle share.

    Example score message (see ``example_message``): the puzzle number in the
    header ("Wordle 1925") is the iteration — everything is keyed off it, not
    the date the share was posted.
    """

    # A full pasted share
    example_message = """Wordle 1925 4/6

⬜⬜⬜⬜🟨
⬜🟩⬜🟨⬜
🟩🟩⬜⬜🟨
🟩🟩🟩🟩🟩
⬜⬜⬜⬜⬜
⬜⬜⬜⬜⬜"""

    game = "wordle"
    score_sort = "asc"  # fewer guesses is better
    game_url = "https://www.nytimes.com/games/wordle/index.html"

    # "Wordle 1925 4/6" or "Wordle 1,925 X/6"
    _header_re = re.compile(
        r"\bWordle\s*#?\s*(?P<number>\d{1,5}(?:,\d{3})*)\s+"
        r"(?P<guesses>\d+|[xX])\s*/\s*(?P<total>\d+)",
        re.IGNORECASE,
    )
    # one row is 5 tiles: green, yellow, or blank (⬜ = letter not in word)
    _row_re = re.compile(r"[\U0001f7e8\U0001f7e9\u2b1b\u2b1c]{5}")

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
            title="Wordle",
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
            [f"Wordle {number} {guesses}/{total}", "", *rows]
        )
        return resp

    def _rows(self, content: str) -> list[str]:
        """Grid rows in the order they appear."""
        return self._row_re.findall(content)
