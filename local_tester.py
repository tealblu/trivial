#!/usr/bin/env python3
"""Lightweight local testing framework for scoreboard parsers."""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import textwrap
import traceback
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import discord

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import DatabaseManager, migrate_user_scores_schema  # noqa: E402
from parsers.base import ScoreParser  # noqa: E402
from parsers.dispatch import select_parser  # noqa: E402
from parsers.registry import discover_parsers  # noqa: E402
from parsers.scoring import (  # noqa: E402
    build_day_scoreboard_embed,
    build_leaderboard_embed,
    build_scoreboard_embed,
    resolve_metric,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# Format "@Alice:1001 :: Wordle 1,234 4/6" lets test inputs come from
# a specific simulated user (display name / nickname:user id).
#
# To simulate a server nickname that differs from the user's global name:
#   @Nickname~Global Name:1001 :: Wordle 1,234 4/6
_AUTHOR_PREFIX = re.compile(
    r"^@(?P<nick>[^:~]+)(?:~(?P<name>[^:]+))?:(?P<uid>\d+)\s*::\s*(?P<content>.*)$",
    re.DOTALL,
)


def split_author(text: str) -> tuple[MockUser | None, str]:
    """If *text* starts with an author prefix, return (MockUser, payload)."""
    m = _AUTHOR_PREFIX.match(text)
    if m:
        nick = m.group("nick")
        name = m.group("name") or nick
        return (
            MockUser(name=name, uid=int(m.group("uid")), nick=nick),
            m.group("content"),
        )
    return None, text

# Mock Discord objects — lightweight stand-ins so parsers never need the bot


class MockUser:
    """Stand-in for discord.Member / discord.User."""

    def __init__(
        self,
        name: str = "TestUser",
        uid: int = 1000,
        nick: str | None = None,
    ) -> None:
        self.id = uid
        self.name = name
        self.nick = nick
        self.display_name = nick or name
        self.discriminator = "0000"
        self.bot = False
        self.mention = f"<@{uid}>"

    def __str__(self) -> str:
        return self.display_name


class MockChannel:
    """Stand-in for discord.TextChannel."""

    def __init__(self, name: str = "test-channel", cid: int = 2000) -> None:
        self.id = cid
        self.name = name

    def __str__(self) -> str:
        return f"#{self.name}"

    async def send(self, **kwargs: object) -> None:  # noqa: ARG002
        raise RuntimeError(
            "MockChannel.send() was called — parsers should return "
            "a ScoreResponse, not send messages directly."
        )


class MockGuild:
    """Stand-in for discord.Guild."""

    def __init__(self, name: str = "Test Server", gid: int = 3000) -> None:
        self.id = gid
        self.name = name
        self.members: dict[int, MockUser] = {}

    def get_member(self, user_id: int) -> MockUser | None:
        return self.members.get(user_id)

    def __str__(self) -> str:
        return self.name


class MockMessage:
    """Stand-in for discord.Message."""

    def __init__(
        self,
        content: str = "",
        author: MockUser | None = None,
        channel: MockChannel | None = None,
        guild: MockGuild | None = None,
        mid: int = 9999,
    ) -> None:
        self.content = content
        self.author = author or MockUser()
        self.channel = channel or MockChannel()
        self.guild = guild or MockGuild()
        self.id = mid
        self.created_at = datetime.now(timezone.utc)
        self.edited_at: datetime | None = None
        self.mentions: list[MockUser] = []
        self.mention_everyone = False
        self.attachments: list[object] = []
        self.embeds: list[discord.Embed] = []
        self.reactions: list[object] = []
        self.reference: object | None = None


# Embed → terminal renderer

_BAR = "─" * 54
_DBL = "═" * 54


def _color_hex(c: discord.Colour | None) -> str:
    """Return a '#RRGGBB' string, or '(default)' if None/0."""
    if c is None:
        return "(default)"
    val = c.value
    return f"#{val:06X}"


def render_embed(embed: discord.Embed) -> str:
    """Turn a discord.Embed into a readable terminal representation."""
    parts: list[str] = [_DBL]

    # Title & URL
    if embed.title:
        parts.append(f"  {embed.title}")
    if embed.url:
        parts.append(f"  {embed.url}")

    # Description — keep line structure (leaderboards are multi-line)
    if embed.description:
        parts.append(_BAR)
        for line in embed.description.splitlines():
            parts.append(textwrap.indent(textwrap.fill(line, 50), "  "))

    # Author
    if embed.author and embed.author.name:
        parts.append(_BAR)
        parts.append(f"  Author: {embed.author.name}")
        if embed.author.url:
            parts.append(f"         {embed.author.url}")

    # Color
    if embed.color and embed.color.value:
        parts.append(f"  Color: {_color_hex(embed.color)}")

    # Fields — keep line structure inside field values
    for field in embed.fields:
        parts.append(_BAR)
        tag = "  [inline]" if field.inline else ""
        parts.append(f"  {field.name}{tag}")
        val = field.value or "(empty)"
        for line in val.splitlines():
            parts.append(textwrap.indent(textwrap.fill(line, 48), "    "))

    # Footer
    if embed.footer and embed.footer.text:
        parts.append(_BAR)
        parts.append(f"  Footer: {embed.footer.text}")

    # Image / Thumbnail
    if embed.image and embed.image.url:
        parts.append(_BAR)
        parts.append(f"  Image: {embed.image.url}")
    if embed.thumbnail and embed.thumbnail.url:
        parts.append(_BAR)
        parts.append(f"  Thumbnail: {embed.thumbnail.url}")

    parts.append(_DBL)
    return "\n".join(parts)


# Parser pipeline — mirrors cogs/scoreboard.py exactly


async def run_input(
    text: str,
    parsers: list[ScoreParser],
    db: DatabaseManager,
    verbose: bool = False,
) -> None:
    """Feed *text* through the parsing pipeline and print what trivial would do."""
    author, payload = split_author(text)
    msg = MockMessage(content=payload, author=author)
    # Register the author in the guild's member cache so nickname
    # resolution via guild.get_member works exactly like production.
    if author is not None:
        msg.guild.members[author.id] = author

    parser = select_parser(parsers, msg)
    if parser is None:
        if verbose:
            print("  → dispatch: no parser matched")
        print("  ⚠  No parser matched this input.")
        return

    try:
        response = parser.parse(msg)
        await parser.record_score(msg, response, db)

        player = response.username or msg.author.display_name
        score = "—" if response.score is None else response.score
        print(f"  Parsed by: {type(parser).__name__}  (game: '{parser.game}')")
        print(
            f"  → recorded {player} · iteration {response.iteration or '—'} · "
            f"{response.day} · score={score}"
            f"{'  ·  ' + str(response.meta) if response.meta else ''}"
        )

        embed = parser.format_response(response)
        print()
        print(render_embed(embed))
    except Exception as exc:
        print(f"  [!] {type(parser).__name__} raised {type(exc).__name__}: {exc}")
        if verbose:
            traceback.print_exc()


# Local database + input modes


async def open_db(path: Path) -> DatabaseManager:
    """Open (creating if needed) the local score database."""
    connection = await aiosqlite.connect(str(path))
    await migrate_user_scores_schema(connection)
    schema = PROJECT_ROOT / "database" / "schema.sql"
    await connection.executescript(schema.read_text(encoding="utf-8"))
    await connection.commit()
    return DatabaseManager(connection=connection)


async def file_mode(
    path: str,
    parsers: list[ScoreParser],
    db: DatabaseManager,
    delimiter: str | None,
    verbose: bool,
) -> None:
    """Read inputs from *path* and run each through the pipeline."""
    p = Path(path)
    if not p.exists():
        print(f"Error: file not found: {path}")
        return

    raw = p.read_text(encoding="utf-8")

    if delimiter:
        inputs = [s.strip() for s in raw.split(delimiter) if s.strip()]
    else:
        inputs = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    if not inputs:
        print("No inputs found in file.")
        return

    print(f"Loaded {len(inputs)} input(s) from {path}\n")

    for i, text in enumerate(inputs, 1):
        print(f"── Input #{i} {'─' * 44}")
        print(f"  {text}")
        print()
        await run_input(text, parsers, db, verbose)
        print()


async def interactive_mode(
    parsers: list[ScoreParser],
    db: DatabaseManager,
    verbose: bool,
) -> None:
    """REPL — type messages, see what trivial would post and record."""
    print()
    print("┌──────────────────────────────────────────────────────┐")
    print("│         Local Parser Tester  (interactive mode)      │")
    print("│  Type a message and press Enter to test parsing.     │")
    print("│  'list' to show parsers · 'quit' / Ctrl-D to exit.  │")
    print("└──────────────────────────────────────────────────────┘")
    print()

    while True:
        try:
            text = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not text:
            continue
        if text.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break
        if text.lower() == "list":
            print(f"  Registered parsers ({len(parsers)}):")
            for p in parsers:
                print(f"    • {type(p).__name__}  (game: '{p.game}')")
            print()
            continue

        await run_input(text, parsers, db, verbose)
        print()


# CLI


def build_cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="local_tester",
        description="Test scoreboard parsers locally without deploying trivial.",
    )
    ap.add_argument(
        "-p", "--prompt",
        type=str,
        metavar="TEXT",
        default=None,
        help="Parse a single string and exit.",
    )
    ap.add_argument(
        "-f", "--file",
        type=str,
        metavar="PATH",
        default=None,
        help="Read inputs from a text file (one per line by default).",
    )
    ap.add_argument(
        "-d", "--delimiter",
        type=str,
        metavar="SEP",
        default=None,
        help="Split multi-message files on this exact line (e.g. '---').",
    )
    ap.add_argument(
        "--db",
        type=str,
        metavar="PATH",
        default="local_test.db",
        help="Where recorded scores are stored (default: ./local_test.db).",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Show which parsers were tried.",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        dest="list_parsers",
        help="List discovered parsers and exit.",
    )
    ap.add_argument(
        "--scores",
        nargs="?",
        const="",
        default=None,
        metavar="GAME",
        dest="scores_game",
        help="Show each game's most recent iteration (same embed as !scores). "
             "Pass a game name to filter, or omit for all games.",
    )
    ap.add_argument(
        "--date",
        type=str,
        metavar="YYYY-MM-DD",
        default=None,
        help="With --scores: show the scores logged on this date instead of "
             "the latest iteration (game iterating mid-day shows both).",
    )
    ap.add_argument(
        "--leaderboard",
        nargs="?",
        const="",
        default=None,
        metavar="GAME",
        dest="leaderboard_game",
        help="Show the top-3-per-game leaderboard, all time "
             "(same embed as !leaderboard). Pass a game name to filter, or "
             "omit for all games.",
    )
    ap.add_argument(
        "--metric",
        type=str,
        metavar="average|top|wins|count",
        default="average",
        help="How to rank players: `average` (mean score, default), `top` "
             "(best single score), `wins` (first-place finishes), or `count` "
             "(games played).",
    )
    return ap


async def amain(args: argparse.Namespace, parsers: list[ScoreParser]) -> None:
    db = await open_db(Path(args.db))
    try:
        print(f"Scores are recorded to: {args.db}\n")

        # ── Score leaderboard mode (mirrors !scores command) ──────────
        if args.scores_game is not None or args.date is not None:
            game = args.scores_game or None  # "" / None → None (all games)
            sort_orders = {p.game: p.score_sort for p in parsers}
            if args.date:
                records = await db.get_scores_for_day(
                    guild_id=3000, day=args.date, game=game
                )
                embed = build_day_scoreboard_embed(
                    records, day=args.date, game=game, sort_orders=sort_orders
                )
            else:
                records = await db.get_scores(guild_id=3000, game=game)
                embed = build_scoreboard_embed(
                    records, game=game, sort_orders=sort_orders
                )
            print(render_embed(embed))
            return

        # ── Top-3-per-game all-time leaderboard mode (mirrors !leaderboard) ──
        if args.leaderboard_game is not None:
            game = args.leaderboard_game or None  # "" → None (all games)
            metric = resolve_metric(args.metric) or "average"
            records = await db.get_all_scores(guild_id=3000, game=game)
            sort_orders = {p.game: p.score_sort for p in parsers}
            embed = build_leaderboard_embed(
                records,
                game=game,
                sort_orders=sort_orders,
                metric=metric,
            )
            print(render_embed(embed))
            return

        # ── Parse-input modes ─────────────────────────────────────────
        if args.prompt:
            text = args.prompt
            print(f"Input: {text}\n")
            await run_input(text, parsers, db, args.verbose)
        elif args.file:
            await file_mode(args.file, parsers, db, args.delimiter, args.verbose)
        else:
            await interactive_mode(parsers, db, args.verbose)
    finally:
        await db.connection.close()


def main() -> None:
    args = build_cli().parse_args()

    # --- Discover parsers ---------------------------------------------------
    print("Discovering parsers …")
    parsers = discover_parsers()
    for p in parsers:
        print(f"  [+] {type(p).__name__}  (game: '{p.game}', sort: {p.score_sort})  ({type(p).__module__})")
    print(f"Found {len(parsers)} parser(s).\n")

    if args.list_parsers:
        for p in parsers:
            print(f"  • {type(p).__name__}  (game: '{p.game}')  ({type(p).__module__})")
        return

    asyncio.run(amain(args, parsers))


if __name__ == "__main__":
    main()
