from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse
from .common import parse_month_day


class MapTapScoreParser(ScoreParser):
    """Parser for www.maptap.gg daily scores.

    Example score message (see ``example_message``): maptap shares identify the
    puzzle by date, not a number, so that date ("September 17" -> 2026-09-17) is
    the iteration — everything is keyed off it, not the date the share was posted.

        www.maptap.gg September 17
        93🏆 99🎯 98🎯 87🎓 62😐
        Final score: 835
    """

    # A full pasted share — the header's date is the iteration.
    example_message = """www.maptap.gg September 17
93🏆 99🎯 98🎯 87🎓 62😐
Final score: 835"""

    game = "maptap"
    score_sort = "desc"  # higher score is better
    game_url = "https://www.maptap.gg"

    # Match individual round results like "93🏆" or "87🎓".
    _round_re = re.compile(r"(\d+)\s*([^\s\d]+)")

    def can_parse(self, message: discord.Message) -> bool:
        # Require the URL AND a "Final score:" line so casual mentions of
        # the site (without an actual score) don't match this parser.
        if "www.maptap.gg" not in message.content:
            return False
        if re.search(r"Final score:\s*\d+", message.content, re.IGNORECASE) is None:
            return False
        # The header must carry the share's own date — that date is the
        # iteration scores are keyed off, so it can't be optional.
        lines = message.content.strip().splitlines()
        return bool(lines) and self._header_date(lines[0]) is not None

    def _header_date(self, line: str) -> str | None:
        """The ``YYYY-MM-DD`` puzzle date in a share header line, or None."""
        first = re.sub(r"www\.maptap\.gg\s*", "", line.strip()).strip().rstrip(".")
        parts = first.split()
        if len(parts) != 2:
            return None
        try:
            return parse_month_day(parts[0], int(parts[1]))
        except ValueError:
            return None

    def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        score = None
        for line in reversed(lines):
            m = re.search(r"Final score:\s*(\d+)", line, re.IGNORECASE)
            if m:
                score = int(m.group(1))
                break

        iteration = self._header_date(lines[0]) if lines else None

        rounds: list[str] = []
        for line in lines:
            for match in self._round_re.finditer(line):
                rounds.append(f"{match.group(1)}{match.group(2)}")

        resp = self._build_response(
            message, title="MapTap", score=score, iteration=iteration
        )

        if rounds:
            resp.description = " ".join(rounds)

        return resp
