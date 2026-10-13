from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class MetazooaScoreParser(ScoreParser):
    """Parser for metazooa.com daily scores.

    Example score message (see ``example_message``): the puzzle number in the
    header ("Animal #1153") is the iteration — everything is keyed off it, not
    the date the share was posted.
    """

    # A full pasted share — the header carries the iteration number.
    example_message = """🦧 Animal #1153 🦔
I figured it out in 5 guesses!
🟥🟨🟨🟨🟩
🔥 1 | Avg. Guesses: 5
metazooa.com"""

    game = "metazooa"
    score_sort = "asc"  # fewer guesses is better
    game_url = "https://metazooa.com"

    # "{emoji} animal #{number} {emoji}" and animal keeps metaflora out
    _header_re = re.compile(
        r"(?P<first>\S+)\s+Animal\s*#\s*(?P<number>\d+)(?:\s+(?P<answer>\S+))?",
        re.IGNORECASE,
    )
    # guess count. number first so "avg. guesses" can't match
    _guesses_re = re.compile(r"(\d+)\s+guesses\b", re.IGNORECASE)
    # "🔥 1 | avg. guesses: 5"
    _stats_re = re.compile(
        r"(\d+)\s*\|\s*Avg\.?\s*Guesses\s*:?\s*([\d.]+)", re.IGNORECASE
    )
    # one square per guess
    _grid_re = re.compile(r"[\U0001f7e5-\U0001f7ec]+")

    def can_parse(self, message: discord.Message) -> bool:
        content = message.content
        if self._header_re.search(content) is None:
            return False
        # needs a count or grid — the URL is optional, so links can be
        # stripped (e.g. to drop the embed); the "Animal #N" header alone
        # already identifies the game.
        return (
            self._guesses_re.search(content) is not None
            or self._grid_re.search(content) is not None
        )

    def parse(self, message: discord.Message) -> ScoreResponse:
        content = message.content

        header = self._header_re.search(content)
        number = header.group("number") if header else ""

        grid_match = self._grid_re.search(content)
        grid = grid_match.group(0) if grid_match else ""

        score: int | None
        guesses = self._guesses_re.search(content)
        if guesses:
            score = int(guesses.group(1))
        else:
            # stumped so count the grid not 0 which would top the board
            score = len(grid) or None

        stats = self._stats_re.search(content)
        streak = stats.group(1) if stats else ""
        average = stats.group(2) if stats else ""

        resp = self._build_response(
            message, title="Metazooa", score=score, iteration=number
        )
        if number:
            resp.meta["number"] = number
        if streak:
            resp.meta["streak"] = streak
        if average:
            resp.meta["average"] = average
        if grid:
            resp.meta["grid"] = grid

        # rebuilt from parts so a one-liner share doesn't repeat
        parts: list[str] = []
        if header:
            header_line = f"{header.group('first')} Animal #{number}"
            if header.group("answer"):
                header_line += f" {header.group('answer')}"
            parts.append(header_line)
        if guesses is None and score is not None:
            # otherwise a full allowance score reads as a solve
            parts.append(f"Not solved — {score} guesses")
        if grid:
            parts.append(grid)
        if stats:
            parts.append(f"🔥 {streak} | Avg. Guesses: {average}")
        if parts:
            resp.description = "\n".join(parts)

        return resp
