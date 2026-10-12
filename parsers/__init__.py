from .base import ScoreParser, ScoreRecord, ScoreResponse
from .dispatch import select_parser
from .registry import discover_parsers, build_game_link_lines
from .scoring import (
    DEFAULT_METRIC,
    METRIC_ALIASES,
    build_day_scoreboard_embed,
    build_leaderboard_embed,
    build_scoreboard_embed,
    resolve_metric,
)

__all__ = [
    "ScoreParser",
    "ScoreRecord",
    "ScoreResponse",
    "DEFAULT_METRIC",
    "METRIC_ALIASES",
    "build_day_scoreboard_embed",
    "build_leaderboard_embed",
    "build_scoreboard_embed",
    "build_game_link_lines",
    "resolve_metric",
    "select_parser",
]