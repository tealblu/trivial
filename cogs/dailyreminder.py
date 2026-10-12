"""Daily games reminder."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from parsers import build_game_link_lines, build_scoreboard_embed
from parsers.registry import discover_parsers
from timeutil import active_streak, now, now_label, yesterday_str

if TYPE_CHECKING:
    from bot import TrivialBot
    from discord.ext.commands import Context

logger = logging.getLogger("trivial")

_REMINDER_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

# Discord caps an embed description at 4096 characters; long player lists
# are split across several embeds so nobody gets dropped.
_DESCRIPTION_LIMIT = 4096


def _lines_to_embeds(
    lines: list[str],
    *,
    title: str,
    footer: str | None,
    color: int,
) -> list[discord.Embed]:
    """Split *lines* into embeds, each staying under the description limit."""
    embeds: list[discord.Embed] = []
    current: list[str] = []
    length = 0
    for line in lines:
        size = len(line) + 2  # line + its trailing newline
        if current and length + size > _DESCRIPTION_LIMIT:
            embeds.append(
                discord.Embed(title=title, description="\n".join(current), color=color)
            )
            current = []
            length = 0
        current.append(line)
        length += size
    if current:
        embeds.append(
            discord.Embed(title=title, description="\n".join(current), color=color)
        )

    if footer:
        for i, embed in enumerate(embeds, 1):
            text = footer if len(embeds) == 1 else f"{footer} · part {i}/{len(embeds)}"
            embed.set_footer(text=text)
    return embeds


class DailyReminder(commands.Cog, name="dailyreminder"):
    """Sends a daily reminder with links, latest scores and players."""

    def __init__(self, bot: TrivialBot) -> None:
        self.bot = bot
        self.parsers = discover_parsers()

    async def cog_load(self) -> None:
        """Start the reminder loop once the cog is added to the bot."""
        self.daily_reminder_loop.start()

    def cog_unload(self) -> None:
        self.daily_reminder_loop.cancel()

    @tasks.loop(minutes=1.0)
    async def daily_reminder_loop(self) -> None:
        """Every minute, fire reminders for guilds whose time has come."""
        for guild in self.bot.guilds:
            try:
                settings = await self.bot.database.get_daily_reminder(guild.id)
            except Exception:
                logger.exception(
                    "Could not read daily reminder settings for guild %s",
                    guild.name,
                )
                continue

            if not settings or not settings["enabled"]:
                continue

            # Each server is its own clock: compare the reminder time and
            # de-duplicate against the day in the server's timezone.
            tz = await self.bot.get_guild_timezone(guild.id)
            current = now(tz)
            current_time = current.strftime("%H:%M")
            today = current.strftime("%Y-%m-%d")

            if settings["reminder_time"] != current_time:
                continue
            if settings["last_fired"] == today:
                continue

            try:
                channel_id = await self.bot.database.get_score_channel(guild.id)
            except Exception:
                logger.exception(
                    "Could not read score channel for guild %s", guild.name
                )
                continue
            if channel_id is None:
                logger.info(
                    "Daily reminder for guild %s has no score channel to post to",
                    guild.name,
                )
                continue

            channel = guild.get_channel_or_thread(channel_id)
            if channel is None:
                logger.info(
                    "Daily reminder for guild %s could not find channel or thread %s",
                    guild.name,
                    channel_id,
                )
                continue

            try:
                embeds = await self.build_reminder_embeds(
                    guild.id, channel, guild=guild
                )
                await channel.send(embeds=embeds, silent=True)
                await self.bot.database.mark_reminder_sent(guild.id, today)
                logger.info(
                    "Sent daily reminder to guild %s in #%s",
                    guild.name,
                    channel.name,
                )
            except Exception:
                logger.exception(
                    "Failed to send daily reminder to guild %s", guild.name
                )

    @daily_reminder_loop.before_loop
    async def before_daily_reminder_loop(self) -> None:
        await self.bot.wait_until_ready()

    def build_reminder_embed(
        self,
        channel: discord.abc.GuildChannel | discord.Thread,
        tz: ZoneInfo | None = None,
    ) -> discord.Embed:
        """List every supported game (with its link) in a Discord embed."""
        lines = build_game_link_lines(self.parsers)

        embed = discord.Embed(
            title="🎮 Daily Games",
            description=(
                f"Time for today's games! Post your result in {channel.mention} "
                "to have it recorded.\n\n" + "\n".join(lines)
            ),
            color=0xBEBEFE,
        )
        embed.set_footer(text=f"Daily reminder · {now_label(tz)}")
        return embed

    async def build_latest_scoreboard_embed(
        self, guild_id: int, guild: discord.Guild | None = None
    ) -> discord.Embed:
        """Build an embed of each game's most recent iteration for *guild_id*."""
        records = await self.bot.database.get_scores(guild_id=guild_id)
        sort_orders = {parser.game: parser.score_sort for parser in self.parsers}
        return build_scoreboard_embed(
            records,
            title="📊 Latest Scores",
            color=0xBEBEFE,
            sort_orders=sort_orders,
            guild=guild,
        )

    async def build_yesterday_players_embeds(
        self,
        guild_id: int,
        guild: discord.Guild | None = None,
        tz: ZoneInfo | None = None,
    ) -> list[discord.Embed]:
        """List every player active yesterday with their current streak.
        """
        yesterday = yesterday_str(tz)
        days_by_user: dict[int, set[str]] = defaultdict(set)
        user_names: dict[int, str] = {}
        for user_id, user_name, day in await self.bot.database.get_play_days(
            guild_id
        ):
            days_by_user[user_id].add(day)
            user_names[user_id] = user_name

        def display_name(user_id: int) -> str:
            if guild is not None:
                member = guild.get_member(user_id)
                if member is not None:
                    return member.display_name
            return user_names.get(user_id, f"<@{user_id}>")

        players = sorted(
            (
                (display_name(user_id), active_streak(days, yesterday))
                for user_id, days in days_by_user.items()
                if yesterday in days
            ),
            key=lambda item: (-item[1], item[0].lower()),
        )
        lines = [
            f"{name} — 🔥 **{streak}** day{'s' if streak != 1 else ''}"
            for name, streak in players
        ]
        return _lines_to_embeds(
            lines,
            title="🔥 Yesterday's Players",
            footer=(
                f"{len(players)} player{'s' if len(players) != 1 else ''} "
                f"· {yesterday}"
            ),
            color=0xBEBEFE,
        )

    async def build_reminder_embeds(
        self,
        guild_id: int,
        channel: discord.abc.GuildChannel | discord.Thread,
        guild: discord.Guild | None = None,
    ) -> list[discord.Embed]:
        """The complete daily reminder as a list of embeds."""
        tz = await self.bot.get_guild_timezone(guild_id)
        return [
            self.build_reminder_embed(channel, tz),
            await self.build_latest_scoreboard_embed(guild_id, guild=guild),
            *await self.build_yesterday_players_embeds(guild_id, guild=guild, tz=tz),
        ]

    @commands.hybrid_group(
        name="dailyreminder",
        description="Manage the daily games reminder.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def dailyreminder(self, context: Context) -> None:
        """
        Manage the daily games reminder.

        :param context: The hybrid command context.
        """
        if context.invoked_subcommand is None:
            embed = discord.Embed(
                description="Please specify a subcommand.\n\n"
                "**Subcommands:**\n"
                "`enable` - Enable the daily reminder (posts to the score channel or thread).\n"
                "`disable` - Disable the daily reminder.\n"
                "`time` - Set the reminder time (24-hour, e.g. `09:00`).\n"
                "`show` - Show the current reminder settings.\n"
                "`test` - Preview the daily reminder in this channel.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="enable",
        description="Enable the daily games reminder.",
    )
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_enable(self, context: Context) -> None:
        """
        Enable the daily games reminder in the server's score channel.
        """
        channel_id = await self.bot.database.get_score_channel(context.guild.id)
        if channel_id is None:
            embed = discord.Embed(
                description="No score channel or thread is set for this server. "
                "Use `/bind` first so the reminder has somewhere to post.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        settings = await self.bot.database.get_daily_reminder(context.guild.id)
        reminder_time = settings["reminder_time"] if settings else "09:00"
        await self.bot.database.set_daily_reminder(
            context.guild.id, enabled=True, reminder_time=reminder_time
        )

        channel = context.guild.get_channel_or_thread(channel_id)
        tz_label = str(await self.bot.get_guild_timezone(context.guild.id))
        embed = discord.Embed(
            description=(
                f"Daily reminder enabled in "
                f"{channel.mention if channel else channel_id} at {reminder_time} ({tz_label})."
            ),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="disable",
        description="Disable the daily games reminder.",
    )
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_disable(self, context: Context) -> None:
        """
        Disable the daily games reminder.
        """
        settings = await self.bot.database.get_daily_reminder(context.guild.id)
        if not settings or not settings["enabled"]:
            embed = discord.Embed(
                description="The daily reminder is already disabled.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        await self.bot.database.set_daily_reminder(
            context.guild.id,
            enabled=False,
            reminder_time=settings["reminder_time"],
        )
        embed = discord.Embed(
            description="Daily reminder disabled.",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="time",
        description="Set the daily reminder time (24-hour).",
    )
    @app_commands.describe(
        time="Reminder time in 24-hour format, e.g. 09:00 or 17:30"
    )
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_time(self, context: Context, time: str) -> None:
        """
        Set the daily reminder time in the server's timezone.
        """
        match = _REMINDER_TIME_RE.match(time.strip())
        if match is None:
            embed = discord.Embed(
                description="Please use 24-hour time, e.g. `09:00` or `17:30`.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        normalized = f"{int(match.group(1)):02d}:{match.group(2)}"
        settings = await self.bot.database.get_daily_reminder(context.guild.id)
        enabled = bool(settings and settings["enabled"])
        await self.bot.database.set_daily_reminder(
            context.guild.id, enabled=enabled, reminder_time=normalized
        )

        state = "enabled" if enabled else "saved (reminder is disabled)"
        tz_label = str(await self.bot.get_guild_timezone(context.guild.id))
        embed = discord.Embed(
            description=f"Daily reminder time set to {normalized} ({tz_label}) ({state}).",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="show",
        description="Show the current daily reminder settings.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_show(self, context: Context) -> None:
        """
        Show the current daily reminder settings.

        :param context: The hybrid command context.
        """
        settings = await self.bot.database.get_daily_reminder(context.guild.id)
        if settings is None:
            embed = discord.Embed(
                description="No daily reminder configured for this server. "
                "Use `/dailyreminder enable` to set one up.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        state = "enabled" if settings["enabled"] else "disabled"
        channel_id = await self.bot.database.get_score_channel(context.guild.id)
        channel = context.guild.get_channel_or_thread(channel_id) if channel_id else None
        tz_label = str(await self.bot.get_guild_timezone(context.guild.id))

        lines = [
            f"**Status:** {state}",
            f"**Time:** {settings['reminder_time']} ({tz_label})",
        ]
        if channel:
            lines.append(f"**Channel:** {channel.mention}")
        elif channel_id:
            lines.append(f"**Channel:** {channel_id}")
        else:
            lines.append("**Channel:** none set — use `/bind` first.")

        embed = discord.Embed(
            title="⏰ Daily Reminder",
            description="\n".join(lines),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="test",
        description="Preview the daily reminder in this channel.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_test(self, context: Context) -> None:
        """
        Send the daily reminder to the current channel
        """
        channel_id = await self.bot.database.get_score_channel(context.guild.id)
        score_channel = (
            context.guild.get_channel_or_thread(channel_id) if channel_id else None
        )

        reference = score_channel or context.channel
        embeds = await self.build_reminder_embeds(
            context.guild.id, reference, guild=context.guild
        )
        await context.send(embeds=embeds, silent=True)


async def setup(bot: TrivialBot) -> None:
    await bot.add_cog(DailyReminder(bot))
