from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import discord

from timeutil import today_str

from .common import format_score

if TYPE_CHECKING:
    from database import DatabaseManager


def message_author_display_name(message: discord.Message) -> str:
    """Return the author's display name, preferring the server nickname."""
    author = message.author
    # A Member exposes the per-server nickname; a plain User does not, so
    # fall back to the cached member to pick up nicknames like production does.
    if not isinstance(author, discord.Member) and message.guild is not None:
        member = message.guild.get_member(author.id)
        if member is not None:
            author = member
    return author.display_name or author.name


@dataclass
class ScoreResponse:
    """Parsed data for one user for one game."""

    title: str = ""
    score: int | None = None  # The value recorded for the user (e.g. guesses)
    game: str = ""  # Falls back to the parser's `game` if left unset
    user_id: int | None = None  # Discord user ID of the scorer
    username: str = ""  # Display name, for logging / embeds
    iteration: str = ""  # The game's own puzzle identifier (e.g. "1925" or "2026-09-18")
    day: str = field(default_factory=today_str)  # YYYY-MM-DD the score was logged (reference only)
    meta: dict[str, str] = field(default_factory=dict)  # e.g. {"number": "1234", "mode": "hard"}
    description: str | None = None
    color: int = 0x2F3136  # Default Discord dark embed color


@dataclass
class ScoreRecord:
    """One row from the ``user_scores`` table used to render leaderboards."""

    user_id: int
    user_name: str
    game: str
    iteration: str
    day: str  # date the score was logged (reference only; never keyed)
    score: int | float
    meta: dict[str, str] | None = None


class ScoreParser(ABC):
    """Base class for game parsers — one parser per game."""

    game: str = ""
    # "asc" = lower is better (fewer guesses); "desc" = higher is better (more points).
    score_sort: Literal["asc", "desc"] = "asc"
    # Link to the game's website, shown in the daily reminder.
    game_url: str = ""
    # Hidden parsers are discovered but excluded from user-facing listings
    # (e.g. the rotating presence and the daily reminder).
    hidden: bool = False

    @abstractmethod
    def can_parse(self, message: discord.Message) -> bool:
        """Return True if the message matches this game's score format."""
        ...

    @abstractmethod
    def parse(self, message: discord.Message) -> ScoreResponse:
        """Extract the author's score and return a ScoreResponse."""
        ...

    def _build_response(
        self,
        message: discord.Message,
        *,
        title: str,
        score: int | float | None,
        iteration: str | None = None,
        day: str | None = None,
    ) -> ScoreResponse:
        """Build a ScoreResponse pre-filled with this game and the author's details.

        :param message: The message the score was extracted from.
        :param title: Title shown on the response embed, e.g. "Color Daily".
        :param score: The numeric score for this game/author/iteration.
        :param iteration: The game's own puzzle identifier — its puzzle number
            (e.g. "1925") or, for date-labelled shares, the share's own date
            as ``YYYY-MM-DD``. Required before the score is saved.
        :param day: Optional log date (``YYYY-MM-DD``); ``None`` keeps today's
            date. Informational only — never used to key or rank scores.
        """
        resp = ScoreResponse(
            title=title,
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message_author_display_name(message),
        )
        if iteration:
            resp.iteration = iteration
        if day:
            resp.day = day
        return resp

    def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        """Default embed: title, description, a Score field, and author/footer.

        Override for a richer per-game embed (e.g. extra fields from ``meta``).
        """
        embed = discord.Embed(
            title=score_response.title,
            description=score_response.description,
            color=score_response.color,
        )
        embed.add_field(
            name="Score", value=format_score(score_response.score), inline=True
        )
        # Footer shows the game's own puzzle identifier: its index number
        # ("#88") or, for date-labelled shares, the parsed date. The date the
        # score was logged is not shown; fall back to it only when a parser
        # never set an iteration.
        iteration = score_response.iteration
        if iteration.isdigit():
            iteration = f"#{iteration}"
        embed.set_footer(
            text=f"{score_response.username} · {iteration or score_response.day}"
        )
        return embed

    async def record_score(
        self,
        message: discord.Message,
        response: ScoreResponse,
        database: DatabaseManager,
    ) -> None:
        """Persist ONE score for this game, tied to the message author."""
        if not self.game:
            raise ValueError(
                f"{type(self).__name__} must define a `game` identifier "
                "(e.g. 'wordle') so scores can be stored per game."
            )
        await database.record_user_score(
            guild_id=message.guild.id if message.guild else 0,
            user_id=response.user_id or message.author.id,
            user_name=response.username or message_author_display_name(message),
            game=self.game,
            iteration=response.iteration,
            score=response.score,
            meta=response.meta,
            day=response.day,
        )
