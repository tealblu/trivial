from __future__ import annotations

import discord

from .base import ScoreParser, ScoreResponse


class ExampleScoreParser(ScoreParser):
    """Skeleton parser — copy this file to add a REAL game parser.

    Every concrete parser MUST set ``ScoreResponse.iteration`` to the game's
    own puzzle identifier — the puzzle number from the share (e.g. Wordle's
    "1925"), or, for games whose share labels the puzzle by date (dialed,
    maptap), the share's own date as ``YYYY-MM-DD``. Scores are keyed off the
    iteration, never the date the message was posted, so boards stay correct
    even when games reset or iterate at different times.

    Example score message (see ``example_message``): the "#123" in the header
    is the puzzle number that becomes the iteration.
    """

    # A full pasted share — must contain the iteration number/date the parser
    # reads out of it. Update this whenever the game changes its share format.
    example_message = """Game Name #123 4/6

🟩🟩🟨⬛⬛
🟩🟩🟩🟩🟩"""

    game = "example"
    hidden = True  # skeleton only: keep out of presence/reminder listings
    # game_url = "https://yourgame.example"  # shown in the daily reminder

    def can_parse(self, message: discord.Message) -> bool:
        # TODO: check message.content against this game's expected format
        return False

    def parse(self, message: discord.Message) -> ScoreResponse:
        # TODO: extract the author's score and the game's puzzle identifier
        # from the message, e.g.:
        #   iteration = header.group("number")   # "123"  (or a YYYY-MM-DD date)
        return self._build_response(
            message,
            title="Example Scores",
            score=None,  # TODO: e.g. number of guesses
            iteration=None,  # TODO: REQUIRED — the puzzle number/date from the share
            # meta={"number": "1234", "mode": "normal"},
        )
