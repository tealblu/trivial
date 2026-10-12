from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class GeosportleScoreParser(ScoreParser):
    """Parser for a pasted Geosportle share (https://geosportle.app).

    Example score message (see ``example_message``): the puzzle number in the
    header ("Geosportle #3") is the iteration — everything is keyed off it, not
    the date the share was posted. Scores run 0–1,000 and higher is better.

    A replay share ("Geosportle #3 (replay) · ...") is deliberately ignored:
    the header regex demands the number be followed immediately by the "·"
    separator, so the "(replay)" text stops it from matching.
    """

    # A full pasted share — the header carries the iteration number and score.
    example_message = """Geosportle #3 · 742/1,000
🟢🟡🎯🟢🟠
⏱ 1:12 · 🔥 5-day streak
geosportle.app/challenge/3/742"""

    game = "geosportle"
    score_sort = "desc"  # higher score is better
    game_url = "https://geosportle.app"

    # "Geosportle #3 · 742/1,000" — puzzle number and score/total. The "·"
    # must follow the number directly so "Geosportle #3 (replay) · ..." fails.
    _header_re = re.compile(
        r"\bGeosportle\s*#\s*(?P<number>\d+)\s*·\s*"
        r"(?P<score>[\d,]+)\s*/\s*(?P<total>[\d,]+)",
        re.IGNORECASE,
    )
    _total = "1000"
    # one emoji per round: coloured circles (🟠🟡🟢…) and the 🎯 hit marker
    _grid_re = re.compile(
        r"[\U0001f7e0-\U0001f7e5\U0001f534\U0001f535\U0001f3af\u26aa\u26ab]{2,}"
    )
    _time_re = re.compile(r"⏱\s*(?P<time>\d+:\d+)")
    _streak_re = re.compile(r"🔥\s*(?P<streak>\d+)\s*-?\s*day", re.IGNORECASE)

    def can_parse(self, message: discord.Message) -> bool:
        # Require the "#N · score/1,000" header so casual mentions of the game
        # (or replays) don't match this parser.
        header = self._header_re.search(message.content)
        if header is None:
            return False
        return header.group("total").replace(",", "") == self._total

    def parse(self, message: discord.Message) -> ScoreResponse:
        content = message.content
        header = self._header_re.search(content)
        number = header.group("number")
        score = int(header.group("score").replace(",", ""))
        total = header.group("total").replace(",", "")

        grid_match = self._grid_re.search(content)
        grid = grid_match.group(0) if grid_match else ""

        time_match = self._time_re.search(content)
        time = time_match.group("time") if time_match else ""

        streak_match = self._streak_re.search(content)
        streak = streak_match.group("streak") if streak_match else ""

        resp = self._build_response(
            message,
            title="Geosportle",
            score=score,
            iteration=number,
        )
        resp.meta.update(
            number=number,
            score=str(score),
            total=total,
        )
        if grid:
            resp.meta["grid"] = grid
        if time:
            resp.meta["time"] = time
        if streak:
            resp.meta["streak"] = streak

        # Rebuilt from parts so a one-liner share doesn't repeat the header.
        parts = [f"Geosportle #{number} · {score:,}/{int(total):,}"]
        if grid:
            parts.append(grid)
        stats = []
        if time:
            stats.append(f"⏱ {time}")
        if streak:
            stats.append(f"🔥 {streak}-day streak")
        if stats:
            parts.append(" · ".join(stats))
        resp.description = "\n".join(parts)
        return resp
