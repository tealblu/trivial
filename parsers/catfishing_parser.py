from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse
from .common import FRACTION_SCORE_RE, parse_fraction_score


class CatfishingScoreParser(ScoreParser):
    """Parser for catfishing.net daily scores.

    Example score message (see ``example_message``): the puzzle number in the
    score line ("#815") is the iteration — everything is keyed off it, not the
    date the share was posted.
    """

    # A full pasted share — the "#N" line carries the iteration number.
    example_message = """catfishing.net
#815
4/10
# # # # █"""

    game = "catfishing"
    score_sort = "desc"  # higher score is better
    game_url = "https://catfishing.net"

    # The share header is its own whole line: "catfishing.net" or "catfishing dot net".
    _header_re = re.compile(
        r"\s*catfishing(?:\s*dot\s*net|\.net)?\s*$", re.IGNORECASE
    )
    # "#815 - 4/10" — puzzle number and correct/total score.
    _number_re = re.compile(r"#\s*(\d+)")
    # Total of the score fraction — "X/10" or "X.Y/10" (see FRACTION_SCORE_RE).
    # Requiring the total filters dates; decimal scores are allowed ("1.5/10").
    _total = "10"

    def can_parse(self, message: discord.Message) -> bool:
        # The share header must be the first line, followed by an "X/10" score line.
        lines = message.content.strip().splitlines()
        if not lines or not self._header_re.match(lines[0]):
            return False
        for line in lines[1:]:
            if parse_fraction_score(line, self._total) is not None:
                return True
        return False

    def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        # The share header is the first line; everything after it is share data.
        share_lines = lines[1:] if lines and self._header_re.match(lines[0]) else lines

        number = ""
        for line in share_lines:
            m = self._number_re.search(line)
            if m:
                number = m.group(1)
                break

        score = None
        total = None
        for line in share_lines:
            parsed = parse_fraction_score(line, self._total)
            if parsed is not None:
                score, _, total = parsed
                break

        grid_lines = [
            line.strip()
            for line in share_lines
            if line.strip() and FRACTION_SCORE_RE.search(line) is None
        ]

        resp = self._build_response(
            message, title="Catfishing", score=score, iteration=number
        )
        if number:
            resp.meta["number"] = number
        if total:
            resp.meta["total"] = total

        header = f"#{number} · {score}/{total}" if number else f"{score}/{total}"
        resp.description = "\n".join([header, *grid_lines])

        return resp
