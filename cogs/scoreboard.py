from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from parsers import (
    DEFAULT_METRIC,
    METRIC_ALIASES,
    ScoreParser,
    build_game_link_lines,
    build_leaderboard_embed,
    build_scoreboard_embed,
    resolve_metric,
    select_parser,
)
from parsers.registry import discover_parsers
from timeutil import day_string

if TYPE_CHECKING:
    from bot import TrivialBot
    from discord.ext.commands import Context

logger = logging.getLogger("trivial")


def _resolve_leaderboard_metric(
    game: str | None,
    metric: str | None,
) -> tuple[str, str | None, str | None]:
    """Resolve which aggregation metric /leaderboard should use.
    """
    metric_key = resolve_metric(metric)
    if metric is not None and metric_key is None:
        first, *rest = METRIC_ALIASES  # dicts keep insertion order
        names = ", ".join([f"`{first}` (default)", *(f"`{name}`" for name in rest)])
        return DEFAULT_METRIC, game, (
            f"`{metric}` is not a valid metric — use {names}."
        )

    # Set explicitly to a metric outside the default family: trust it untouched.
    if (
        metric is not None
        and metric_key is not None
        and metric.strip().lower() not in METRIC_ALIASES[DEFAULT_METRIC]
    ):
        return metric_key, game, None

    # metric untouched (default): pick up a metric keyword from the game slot,
    # so `!leaderboard top` reads as "rank all games by best score".
    if game is not None and resolve_metric(game) is not None:
        metric_key = resolve_metric(game)
        game = None
    return metric_key or DEFAULT_METRIC, game, None


class Scoreboard(commands.Cog):
    """Listens for messages containing game scores and posts parsed results."""

    def __init__(self, bot: TrivialBot) -> None:
        self.bot = bot
        self._tracked_channels: dict[int, int] = {}  # guild_id -> channel_id

        self.parsers: list[ScoreParser] = discover_parsers()
        for parser in self.parsers:
            logger.info(
                "Registered parser: %s (game: %s)", type(parser).__name__, parser.game
            )

    async def _get_tracked_channel(self, guild_id: int) -> int | None:
        """Return the monitored channel ID for *guild_id*, or None."""
        if guild_id not in self._tracked_channels:
            self._tracked_channels[guild_id] = (
                await self.bot.database.get_score_channel(guild_id)
            )
        return self._tracked_channels[guild_id]

    @commands.hybrid_group(
        name="scorechannel",
        description="Manage the channel trivial monitors for scores.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def scorechannel(self, context: Context) -> None:
        """
        Manage the channel trivial monitors for scores.

        :param context: The hybrid command context.
        """
        if context.invoked_subcommand is None:
            embed = discord.Embed(
                description="Please specify a subcommand.\n\n**Subcommands:**\n`set` - Set the channel to monitor for scores.\n`remove` - Stop monitoring scores in this server.\n`show` - Show the currently monitored channel.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)

    @scorechannel.command(
        name="set",
        description="Set the channel trivial monitors for scores.",
    )
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel to monitor for score messages.")
    async def scorechannel_set(
        self, context: Context, channel: discord.TextChannel
    ) -> None:
        """
        Set the channel trivial monitors for scores.
        """
        await self.bot.database.set_score_channel(context.guild.id, channel.id)
        self._tracked_channels[context.guild.id] = channel.id
        embed = discord.Embed(
            description=f"Now monitoring scores in {channel.mention}.",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @scorechannel.command(
        name="remove",
        description="Stop monitoring scores in this server.",
    )
    @commands.has_permissions(manage_guild=True)
    async def scorechannel_remove(self, context: Context) -> None:
        """
        Stop monitoring scores in this server.

        :param context: The hybrid command context.
        """
        await self.bot.database.remove_score_channel(context.guild.id)
        self._tracked_channels.pop(context.guild.id, None)
        embed = discord.Embed(
            description="Stopped monitoring scores in this server.",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @scorechannel.command(
        name="show",
        description="Show the currently monitored score channel.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def scorechannel_show(self, context: Context) -> None:
        """
        Show the currently monitored score channel.
        """
        channel_id = await self._get_tracked_channel(context.guild.id)
        if channel_id is None:
            embed = discord.Embed(
                description="No score channel is set for this server. Use `/scorechannel set` to configure one.",
                color=0xE02B2B,
            )
        else:
            channel = context.guild.get_channel(channel_id)
            embed = discord.Embed(
                description=f"Trivial monitors scores in {channel.mention if channel else channel_id}.",
                color=0xBEBEFE,
            )
        await context.send(embed=embed, silent=True)

    @commands.hybrid_command(
        name="scores",
        description="Show each game's most recent iteration of scores.",
    )
    @commands.guild_only()
    @app_commands.describe(
        game="Optional game identifier to filter by, e.g. wordle.",
    )
    async def scores(
        self,
        context: Context,
        game: str | None = None,
    ) -> None:
        """
        Show scores for the latest iteration of each game.

        Scores are keyed off each game's own puzzle iteration, so this always
        shows the most recent puzzle of every game, regardless of when games
        reset or iterate.

        Usage:
            !scores        — latest iteration of every game
            !scores wordle — latest iteration of wordle
        """
        # Ack immediately — the leaderboard query over a large (e.g. freshly
        # backfilled) table can outlast Discord's 3-second interaction window.
        # Deferring turns the response into a followup and gives us 15 minutes,
        # avoiding "Unknown interaction" (10062) errors.
        await context.defer()

        records = await context.bot.database.get_scores(
            guild_id=context.guild.id,
            game=game,
        )
        sort_orders = {p.game: p.score_sort for p in self.parsers}
        embed = build_scoreboard_embed(
            records,
            game=game,
            sort_orders=sort_orders,
            guild=context.guild,
        )
        await context.send(embed=embed, silent=True)

    @commands.hybrid_command(
        name="leaderboard",
        description="Show the top 3 players for each game's latest iteration.",
    )
    @commands.guild_only()
    @app_commands.describe(
        game="Optional game identifier to filter by, e.g. wordle.",
        metric="Rank by `average` (default), `top` best score, `wins`, or `count` plays.",
    )
    async def leaderboard(
        self,
        context: Context,
        game: str | None = None,
        metric: str = "average",
    ) -> None:
        """
        Show the top 3 players for each game's most recent iteration.
        """
        # Ack immediately — the same reasons as /scores: a query over a large
        # (e.g. freshly backfilled) table can outlast Discord's 3-second
        # interaction window.
        await context.defer()

        metric_key, game, metric_error = _resolve_leaderboard_metric(game, metric)
        if metric_error is not None:
            embed = discord.Embed(description=metric_error, color=0xE02B2B)
            await context.send(embed=embed, silent=True)
            return

        records = await context.bot.database.get_scores(
            guild_id=context.guild.id,
            game=game,
        )
        sort_orders = {p.game: p.score_sort for p in self.parsers}
        embed = build_leaderboard_embed(
            records,
            game=game,
            sort_orders=sort_orders,
            guild=context.guild,
            metric=metric_key,
        )
        await context.send(embed=embed, silent=True)

    @commands.hybrid_command(
        name="games",
        description="List every supported game with a link to play.",
    )
    async def games(self, context: Context) -> None:
        """
        List the supported games and links to their websites.

        Usage:
            !games
        """
        lines = build_game_link_lines(self.parsers)
        embed = discord.Embed(
            title="🎮 Supported Games",
            description="\n".join(lines),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @commands.hybrid_command(
        name="nuke",
        description="Delete all recorded scores for this server (admins only).",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        confirm="Type 'confirm' to permanently delete this server's scores."
    )
    async def nuke(self, context: Context, confirm: str = "") -> None:
        """
        Delete every recorded score for this server.

        Only this server's leaderboard rows are removed.

        Usage:
            !nuke          — shows what this command does
            !nuke confirm  — permanently deletes this server's scores
        """
        if confirm.strip().lower() != "confirm":
            embed = discord.Embed(
                description=(
                    "⚠️ This **permanently deletes every recorded score** for "
                    f"**{context.guild.name}** — every game's latest-iteration "
                    "boards will start empty.\n\n"
                    "Run `/nuke confirm` (or `!nuke confirm`) to proceed."
                ),
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        deleted = await self.bot.database.delete_guild_scores(context.guild.id)
        embed = discord.Embed(
            description=(
                f"💥 Deleted **{deleted}** score{'s' if deleted != 1 else ''} "
                f"for **{context.guild.name}**. Leaderboards are now empty."
            ),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @commands.hybrid_command(
        name="backfill",
        description="Record score messages from the score channel's history.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        limit="How many messages to scan (default: 200; 0 = all history).",
        days="Only scan messages posted in the last N days (default: all).",
    )
    async def backfill(
        self,
        context: Context,
        limit: int = 200,
        days: int | None = None,
    ) -> None:
        """
        Scan the score channel's message history and record any score
        messages into the database.

        Usage:
            !backfill         — scan the last 200 messages
            !backfill 1000    — scan the last 1000 messages
            !backfill 0       — scan the entire history
            !backfill 0 7     — entire history but only the last 7 days
        """
        channel_id = await self._get_tracked_channel(context.guild.id)
        if channel_id is None:
            embed = discord.Embed(
                description="No score channel is set for this server. Use `/scorechannel set` first.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        channel = context.guild.get_channel(channel_id)
        if channel is None:
            embed = discord.Embed(
                description="The configured score channel could not be found.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        limit_desc = "all" if limit <= 0 else f"up to **{limit}**"
        await context.send(
            embed=discord.Embed(
                description=f"🔍 Scanning {limit_desc} messages in {channel.mention}…",
                color=0xBEBEFE,
            ),
            silent=True,
        )

        kwargs: dict = {}
        # discord.py's history() silently caps at 100 messages by default
        # when limit is 0 (or negative) the command promises "all history",
        # so pass limit=None explicitly to disable that cap.
        kwargs["limit"] = limit if limit > 0 else None
        if days is not None:
            kwargs["after"] = datetime.now(timezone.utc) - timedelta(days=days)

        scanned = 0
        recorded = 0
        games: dict[str, int] = {}
        seen: set[tuple[int, str, str]] = set()

        async for message in channel.history(**kwargs):
            if message.author.bot:
                continue
            scanned += 1
            try:
                parser = select_parser(self.parsers, message)
                if parser is None:
                    continue
                response = parser.parse(message)
                # The log date is the date the message was posted; scores are
                # keyed by the puzzle iteration, so this is reference only.
                response.day = day_string(message.created_at)
                key = (message.author.id, parser.game, response.iteration)
                if key in seen:
                    continue  # a newer post for this player/game/iteration is recorded
                seen.add(key)
                await parser.record_score(message, response, self.bot.database)
                recorded += 1
                games[parser.game] = games.get(parser.game, 0) + 1
            except Exception:
                logger.exception(
                    "Backfill: parser %s failed on message %s",
                    type(parser).__name__ if parser else "?",
                    message.id,
                )

        game_list = ", ".join(
            f"{name} × {count}" for name, count in sorted(games.items())
        )
        embed = discord.Embed(
            description=(
                f"✅ Scanned **{scanned}** message(s) in {channel.mention}.\n"
                f"Recorded **{recorded}** score(s)"
                + (f" ({game_list})" if game_list else "")
                + ".\n"
            ),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        tracked_channel = await self._get_tracked_channel(message.guild.id)
        if tracked_channel is None or message.channel.id != tracked_channel:
            return

        parser = select_parser(self.parsers, message)
        if parser is None:
            return

        try:
            score_response = parser.parse(message)
            # Persist before posting so a daily result is never lost if the
            # embed fails.
            await parser.record_score(message, score_response, self.bot.database)
            embed = parser.format_response(score_response)
            await message.channel.send(embed=embed, silent=True)
            logger.info(
                "Recorded %s score for %s in #%s using %s",
                parser.game,
                message.author,
                message.channel,
                type(parser).__name__,
            )
        except Exception:
            logger.exception(
                "Parser %s failed on message %s",
                type(parser).__name__,
                message.id,
            )


async def setup(bot: TrivialBot) -> None:
    await bot.add_cog(Scoreboard(bot))
