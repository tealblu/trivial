"""Per-server timezone settings.

Every server uses the bot's default timezone (the ``TIMEZONE`` env var, UTC
when unset) unless an admin sets an override here. The override controls the
calendar day scores are logged under and when the daily reminder fires.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

from timeutil import bot_tz, now

if TYPE_CHECKING:
    from bot import TrivialBot

logger = logging.getLogger("trivial")


class Timezone(commands.Cog, name="timezone"):
    """Show or change this server's timezone."""

    def __init__(self, bot: TrivialBot) -> None:
        self.bot = bot

    @commands.hybrid_group(
        name="timezone",
        description="Show or change this server's timezone.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def timezone(self, context: Context) -> None:
        """
        Manage this server's timezone.

        :param context: The hybrid command context.
        """
        if context.invoked_subcommand is None:
            embed = discord.Embed(
                description=(
                    "Please specify a subcommand.\n\n**Subcommands:**\n"
                    "`set` - Set this server's timezone (IANA name).\n"
                    "`reset` - Go back to the bot's default timezone.\n"
                    "`show` - Show the current timezone."
                ),
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)

    @timezone.command(
        name="set",
        description="Set this server's timezone.",
    )
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        zone="IANA timezone name, e.g. America/New_York or Asia/Tokyo."
    )
    async def timezone_set(self, context: Context, zone: str) -> None:
        """
        Set this server's timezone to *zone*.
        """
        try:
            tz = await self.bot.set_guild_timezone(context.guild.id, zone)
        except ValueError:
            embed = discord.Embed(
                description=(
                    f"`{zone}` is not a valid IANA timezone name. Try "
                    "something like `America/New_York`, `Europe/London` or "
                    "`Asia/Tokyo`."
                ),
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        current = now(tz)
        embed = discord.Embed(
            description=(
                f"Timezone set to **{tz.key}**.\n"
                f"Current server time: {current.strftime('%H:%M')} "
                f"({current.strftime('%Y-%m-%d')})."
            ),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @timezone.command(
        name="reset",
        description="Use the bot's default timezone again.",
    )
    @commands.has_permissions(manage_guild=True)
    async def timezone_reset(self, context: Context) -> None:
        """
        Drop this server's timezone override.
        """
        tz = await self.bot.set_guild_timezone(context.guild.id, None)
        embed = discord.Embed(
            description=f"Timezone reset to the bot default (**{tz.key}**).",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @timezone.command(
        name="show",
        description="Show this server's current timezone.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def timezone_show(self, context: Context) -> None:
        """
        Show this server's effective timezone.
        """
        override = await self.bot.database.get_guild_timezone(context.guild.id)
        tz = await self.bot.get_guild_timezone(context.guild.id)
        source = (
            "set for this server"
            if override
            else f"bot default (`TIMEZONE` env, currently {bot_tz()})"
        )
        current = now(tz)
        embed = discord.Embed(
            title="🕐 Server Timezone",
            description=(
                f"**Timezone:** {tz.key}\n"
                f"**Source:** {source}\n"
                f"**Current time:** {current.strftime('%Y-%m-%d %H:%M')}"
            ),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)


async def setup(bot: TrivialBot) -> None:
    await bot.add_cog(Timezone(bot))
