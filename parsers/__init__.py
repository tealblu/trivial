from .base import ScoreParser, ScoreRecord, ScoreResponse
from .dispatch import select_parser
from .registry import (
    build_game_link_lines,
    build_game_table_markdown,
    discover_parsers,
)
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
    "build_game_table_markdown",
    "resolve_metric",
    "select_parser",
]