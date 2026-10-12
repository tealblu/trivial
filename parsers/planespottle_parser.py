from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class PlanespottleScoreParser(ScoreParser):
    """Parser for a pasted Planespottle share.

    Example score message (see ``example_message``): the puzzle number in the
    header ("Planespottle 285/2026") is the iteration — everything is keyed
    off it, not the date the share was posted.
    """

    # A full pasted share
    example_message = """Planespottle 285/2026 in 2/5 guesses!

✅✅✅
✅✅❌
https://planespottle.net/daily"""

    game = "planespottle"
    score_sort = "asc"  # fewer guesses is better
    game_url = "https://planespottle.net"

    # "Planespottle 285/2026 in 2/5 guesses!" — puzzle number and score.
    # The "in" keyword separates the allowance from the guess count.
    _header_re = re.compile(
        r"\bPlanespottle\s+(?P<number>\d+)/(?P<total>\d+)\s+in\s+(?P<guesses>\d+)\s*/\s*(?P<total_guesses>\d+)\s+guesses!",
        re.IGNORECASE,
    )
    # one row is 3+ tiles: ✅ (correct) or ❌ (wrong)
    _row_re = re.compile(r"[✅❌]+")

    def can_parse(self, message: discord.Message) -> bool:
        content = message.content
        if self._header_re.search(content) is None:
            return False
        # Require at least one grid row so a bare header without tiles doesn't match.
        if not self._rows(content):
            return False
        return True

    def parse(self, message: discord.Message) -> ScoreResponse:
        header = self._header_re.search(message.content)
        number = header.group("number")
        total = header.group("total")
        guesses = header.group("guesses")
        total_guesses = header.group("total_guesses")
        rows = self._rows(message.content)

        # get score from header — fewer guesses is better
        score = int(guesses)

        resp = self._build_response(
            message,
            title="Planespottle",
            score=score,
            iteration=number,
        )
        resp.meta.update(
            number=number,
            total=total,
            guesses=guesses,
            total_guesses=total_guesses,
            grid="\n".join(rows),
        )
        resp.description = "\n".join(
            [f"Planespottle {number}/{total} in {guesses}/{total_guesses} guesses!", "", *rows]
        )
        return resp

    def _rows(self, content: str) -> list[str]:
        """Grid rows in the order they appear."""
        return self._row_re.findall(content)