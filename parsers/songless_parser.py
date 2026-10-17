from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class SonglessScoreParser(ScoreParser):
    """Parser for a pasted Songless share."""

    example_message = """I found the All song in 0.1 seconds 🤯 [Songless tealblu/trivial#415]

🟩⬛⬛⬛⬛ [All]
🟥🟥🟥🟥🟥 [Rock]
🟥🟥🟥🟥🟥 [Hip Hop]

Play Today's Game: https://less.gg/songless"""

    game = "songless"
    score_sort = "asc"  # fewer seconds is better
    game_url = "https://less.gg/songless"

    _share_re = re.compile(
        r"\bSongless\b.*?(?:#|tealblu/trivial#)(?P<number>\d+)",
        re.IGNORECASE,
    )
    _time_re = re.compile(
        r"\b(?:I\s+found|I\s+got|I\s+solved|found|got|solved)\s+"
        r"the\s+(?P<song>[A-Za-z0-9' -]+?)\s+song\s+in\s+"
        r"(?P<seconds>\d+(?:\.\d+)?)\s+seconds",
        re.IGNORECASE,
    )
    _row_re = re.compile(
        r"^(?:🟩\uFE0F?|🟥\uFE0F?|⬛\uFE0F?|⬜\uFE0F?|🟨\uFE0F?){5}$",
        re.MULTILINE,
    )

    def can_parse(self, message: discord.Message) -> bool:
        content = message.content
        lower = content.lower()
        if "songless" not in lower:
            return False
        if self._time_re.search(content) is None and self._share_re.search(content) is None:
            return False
        return True

    def parse(self, message: discord.Message) -> ScoreResponse:
        content = message.content
        share_match = self._share_re.search(content)
        time_match = self._time_re.search(content)

        if share_match is None and time_match is None:
            raise ValueError("Songless message is missing both an issue number and a time score")

        number = share_match.group("number") if share_match is not None else None
        score = float(time_match.group("seconds")) if time_match is not None else None
        song = time_match.group("song").strip() if time_match is not None else ""
        rows = self._rows(content)

        resp = self._build_response(
            message,
            title="Songless",
            score=score,
            iteration=number,
        )
        if song:
            resp.meta["song"] = song
        if time_match is not None:
            resp.meta["seconds"] = time_match.group("seconds")
        if rows:
            resp.meta["grid"] = "\n".join(rows)

        header = f"Songless #{number}" if number else "Songless"
        if time_match is not None:
            header = f"{header} · {score} seconds"
        parts = [header]
        if song and time_match is not None:
            parts.append(f"I found the {song} song in {time_match.group('seconds')} seconds")
        if rows:
            parts.extend(rows)
        resp.description = "\n".join(parts)
        return resp

    def _rows(self, content: str) -> list[str]:
        """Grid rows in the order they appear."""
        return self._row_re.findall(content)
