from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse
from .common import FRACTION_SCORE_RE, parse_fraction_score, parse_month_day


class DialedScoreParser(ScoreParser):
    """Parser for dialed.gg daily scores — specifically the Color Daily.

    Example score message (see ``example_message``): dialed shares identify the
    puzzle by date, not a number, so that date ("Sep 18" -> 2026-09-18) is the
    iteration — everything is keyed off it, not the date the share was posted.

        Color Daily — Sep 18
        40.49/50 🟩🟨🟨🟧🟨
        https://dialed.gg/color?d=1&s=40.49
    """

    # A full pasted share — the header's date is the iteration.
    example_message = """Color Daily — Sep 18
40.49/50 🟩🟨🟨🟧🟨
https://dialed.gg/color?d=1&s=40.49"""

    game = "dialed"
    score_sort = "desc"  # higher score is better
    game_url = "https://dialed.gg/color"

    # The daily share header — everything else dialed posts is ignored.
    _header_re = re.compile(r"Color\s+Daily", re.IGNORECASE)
    # Date inside the header, e.g. "Sep 18" — the share's own puzzle date.
    _date_re = re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b",
        re.IGNORECASE,
    )

    def can_parse(self, message: discord.Message) -> bool:
        content = message.content
        # Only the Color Daily share — other dialed games/modes never match.
        if self._header_re.search(content) is None:
            return False
        # Require a "X/50" score line so a text-only mention of the game
        # doesn't match (and can't record a None score). The share URL is
        # optional — it can be stripped (e.g. to drop the embed) and the
        # header + score line still identify the share.
        if parse_fraction_score(content, "50") is None:
            return False
        # The header must carry the share's own date — that date is the
        # iteration scores are keyed off, so it can't be optional.
        lines = content.strip().splitlines()
        return bool(lines) and self._date_re.search(lines[0]) is not None

    def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        score: float | None = None
        total: str | None = None
        raw_score: str | None = None
        for line in lines:
            parsed = parse_fraction_score(line)
            if parsed is not None:
                score, raw_score, total = parsed
                break

        iteration = ""
        if lines:
            date_match = self._date_re.search(lines[0])
            if date_match is not None:
                iteration = parse_month_day(
                    date_match.group(1), int(date_match.group(2))
                ) or ""

        tiles = ""
        for line in lines:
            match = FRACTION_SCORE_RE.search(line)
            if match:
                tiles = FRACTION_SCORE_RE.sub("", line).strip()
                break

        resp = self._build_response(
            message, title="Color Daily", score=score, iteration=iteration
        )
        if raw_score:
            resp.meta["score"] = raw_score
        if total:
            resp.meta["total"] = total
        if tiles:
            resp.meta["tiles"] = tiles

        header = lines[0].strip() if lines else "Color Daily"
        score_line = " ".join(
            part for part in (f"{raw_score or ''}/{total or ''}".rstrip("/"), tiles) if part
        )
        resp.description = "\n".join([header, score_line])

        return resp
