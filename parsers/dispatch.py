"""Message → parser dispatch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import ScoreParser

if TYPE_CHECKING:
    import discord

logger = logging.getLogger("trivial")


def select_parser(
    parsers: list[ScoreParser],
    message: discord.Message,
) -> ScoreParser | None:
    """Return the parser that should handle the message, or None."""
    for parser in parsers:
        try:
            if parser.can_parse(message):
                return parser
        except Exception:
            logger.exception(
                "Parser %s failed during can_parse on message %s",
                type(parser).__name__,
                getattr(message, "id", "?"),
            )
    return None
