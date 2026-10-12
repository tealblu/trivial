"""
Owner-only commands to register (or unregister) the bot's slash commands
with Discord. The bot also auto-syncs on startup, so these exist for when
I change a command and want to push the new tree without a restart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

if TYPE_CHECKING:
    from bot import TrivialBot


class Sync(commands.Cog, name="sync"):
    def __init__(self, bot: TrivialBot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="sync",
        description="Sync slash commands with Discord (global or guild).",
    )
    @commands.is_owner()
    @app_commands.describe(scope="The scope of the sync. Can be `global` or `guild`")
    async def sync(self, context: Context, scope: str) -> None:
        """
        Register the bot's slash commands with Discord.
        """
        if scope == "global":
            await self.bot.tree.sync()
            description = "Slash commands have been globally synchronized."
        elif scope == "guild":
            self.bot.tree.clear_commands(guild=context.guild)
            await self.bot.tree.sync(guild=context.guild)
            description = (
                "Guild-specific commands cleared; this guild now uses the global command tree."
            )
        else:
            embed = discord.Embed(
                description="The scope must be `global` or `guild`.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return
        embed = discord.Embed(description=description, color=0xBEBEFE)
        await context.send(embed=embed, silent=True)

    @commands.hybrid_command(
        name="unsync",
        description="Remove the bot's slash commands (global or guild).",
    )
    @commands.is_owner()
    @app_commands.describe(scope="The scope of the unsync. Can be `global` or `guild`")
    async def unsync(self, context: Context, scope: str) -> None:
        """
        Unregister the bot's slash commands with Discord.
        """
        if scope == "global":
            self.bot.tree.clear_commands(guild=None)
            await self.bot.tree.sync()
            description = "Slash commands have been globally unsynchronized."
        elif scope == "guild":
            self.bot.tree.clear_commands(guild=context.guild)
            await self.bot.tree.sync(guild=context.guild)
            description = "Slash commands have been unsynchronized in this guild."
        else:
            embed = discord.Embed(
                description="The scope must be `global` or `guild`.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return
        embed = discord.Embed(description=description, color=0xBEBEFE)
        await context.send(embed=embed, silent=True)


async def setup(bot: TrivialBot) -> None:
    await bot.add_cog(Sync(bot))
