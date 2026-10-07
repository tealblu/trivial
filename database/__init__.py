"""
Copyright © Krypton 2019-Present - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized Discord bot in Python

Version: 6.5.0
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    from parsers.base import ScoreRecord


def _iteration_key(value: str) -> tuple[int, int | str]:
    """Ordering key for an iteration string.

    Numeric puzzles (e.g. Wordle "1925") must compare numerically so that
    "999" is older than "1000" — a plain string sort gets that wrong.
    Anything else (e.g. dialed/maptap YYYY-MM-DD share dates) compares
    lexicographically, which is correct for ISO dates.
    """
    try:
        return 0, int(value)
    except ValueError:
        return 1, value


async def migrate_user_scores_schema(connection: aiosqlite.Connection) -> None:
    """Rebuild an old day-keyed ``user_scores`` table as iteration-keyed.

    Pre-iteration databases stored one row per (guild, user, game, day).
    This rebuilds the table so the primary key is
    (guild_id, user_id, game, iteration). Rows whose ``meta`` JSON carries a
    ``number`` (wordle, krillion, catfishing, metazooa) are kept with that
    iteration; dialed/maptap rows have no puzzle number, so they are dropped
    (re-record them with ``!backfill``). Fresh or already-migrated tables are
    left untouched. Run BEFORE executing ``schema.sql`` so its indexes can be
    created against the new shape.
    """
    cursor = await connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_scores'"
    )
    if await cursor.fetchone() is None:
        return

    cursor = await connection.execute("PRAGMA table_info(user_scores)")
    columns = await cursor.fetchall()
    if any(row[1] == "iteration" for row in columns):
        return

    await connection.executescript(
        """
        BEGIN;
        CREATE TABLE user_scores_migrated (
          `guild_id`   varchar(20)  NOT NULL,
          `user_id`    varchar(20)  NOT NULL,
          `game`       varchar(32)  NOT NULL,
          `iteration`  varchar(32)  NOT NULL,
          `score`      real         NOT NULL,
          `user_name`  varchar(255) NOT NULL,
          `meta`       text         NULL,
          `day`        varchar(10)  NOT NULL,
          `created_at` timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (`guild_id`, `user_id`, `game`, `iteration`)
        );
        INSERT INTO user_scores_migrated
            (guild_id, user_id, user_name, game, iteration, score, meta, day, created_at)
          SELECT guild_id, user_id, user_name, game,
                 json_extract(meta, '$.number'),
                 score, meta, day, created_at
          FROM user_scores
          WHERE json_extract(meta, '$.number') IS NOT NULL;
        DROP TABLE user_scores;
        ALTER TABLE user_scores_migrated RENAME TO user_scores;
        COMMIT;
        """
    )
    await connection.commit()


class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def set_score_channel(self, server_id: int, channel_id: int) -> None:
        """Set the channel trivial monitors for scores in a server."""
        await self.connection.execute(
            "INSERT INTO score_channels(server_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(server_id) DO UPDATE SET channel_id=excluded.channel_id",
            (str(server_id), str(channel_id)),
        )
        await self.connection.commit()

    async def get_score_channel(self, server_id: int) -> int | None:
        """Get the channel trivial monitors for scores in a server."""
        rows = await self.connection.execute(
            "SELECT channel_id FROM score_channels WHERE server_id=?",
            (str(server_id),),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return int(result[0]) if result is not None else None

    async def remove_score_channel(self, server_id: int) -> None:
        """Remove the monitored score channel from a server."""
        await self.connection.execute(
            "DELETE FROM score_channels WHERE server_id=?",
            (str(server_id),),
        )
        await self.connection.commit()

    async def set_daily_reminder(
        self,
        server_id: int,
        enabled: bool,
        reminder_time: str,
    ) -> None:
        """Upsert the daily reminder settings for a server."""
        await self.connection.execute(
            "INSERT INTO daily_reminders(server_id, enabled, reminder_time) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(server_id) DO UPDATE SET "
            "enabled=excluded.enabled, reminder_time=excluded.reminder_time, "
            "last_fired=NULL, updated_at=CURRENT_TIMESTAMP",
            (
                str(server_id),
                1 if enabled else 0,
                reminder_time,
            ),
        )
        await self.connection.commit()

    async def get_daily_reminder(self, server_id: int) -> dict | None:
        """Get the daily reminder settings for a server, or None if unset."""
        rows = await self.connection.execute(
            "SELECT enabled, reminder_time, last_fired "
            "FROM daily_reminders WHERE server_id=?",
            (str(server_id),),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            if result is None:
                return None
            return {
                "enabled": bool(result[0]),
                "reminder_time": result[1],
                "last_fired": result[2],
            }

    async def mark_reminder_sent(self, server_id: int, day: str) -> None:
        """Record that the daily reminder was sent for *day* so it doesn't re-fire."""
        await self.connection.execute(
            "UPDATE daily_reminders SET last_fired=? WHERE server_id=?",
            (day, str(server_id)),
        )
        await self.connection.commit()

    async def record_user_score(
        self,
        guild_id: int,
        user_id: int,
        user_name: str,
        game: str,
        iteration: str,
        score: int | float | None,
        meta: dict[str, str] | None = None,
        day: str = "",
    ) -> None:
        """Log one user's score for one puzzle iteration of one game."""
        if score is None:
            raise ValueError(
                "record_user_score requires a numeric score; "
                "parser did not set ScoreResponse.score"
            )
        if not iteration:
            raise ValueError(
                "record_user_score requires an iteration (the game's own puzzle "
                "identifier); parser did not set ScoreResponse.iteration"
            )
        if not day:
            raise ValueError(
                "record_user_score requires a day — the date the score was "
                "logged (reference only, but still stored on every row)"
            )

        await self.connection.execute(
            "INSERT INTO user_scores "
            "(guild_id, user_id, user_name, game, iteration, score, meta, day) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(guild_id, user_id, game, iteration) DO UPDATE SET "
            "score = excluded.score, user_name = excluded.user_name, "
            "meta = excluded.meta, day = excluded.day, "
            "created_at = CURRENT_TIMESTAMP",
            (
                str(guild_id),
                str(user_id),
                user_name,
                game,
                iteration,
                score,
                json.dumps(meta) if meta else None,
                day,
            ),
        )
        await self.connection.commit()

    async def delete_guild_scores(self, guild_id: int) -> int:
        """Delete every recorded score for the given guild."""
        cursor = await self.connection.execute(
            "DELETE FROM user_scores WHERE guild_id = ?", (str(guild_id),)
        )
        await self.connection.commit()
        return cursor.rowcount

    async def get_play_days(self, guild_id: int) -> list[tuple[int, str, str]]:
        """Fetch one row per (user, day) a score was recorded for a guild."""
        cursor = await self.connection.execute(
            "SELECT user_id, MAX(user_name), day FROM user_scores "
            "WHERE guild_id = ? GROUP BY user_id, day ORDER BY day, user_id",
            (str(guild_id),),
        )
        rows = await cursor.fetchall()
        return [(int(row[0]), row[1], row[2]) for row in rows]

    async def get_scores(
        self,
        guild_id: int,
        game: str | None = None,
    ) -> list[ScoreRecord]:
        """Fetch each game's MOST RECENT iteration rows for a guild.

        Scores are keyed by the game's own puzzle iteration, so the "current"
        board is the latest iteration of every game that has been played.
        Optionally filter to a single *game*.
        """
        from parsers.base import ScoreRecord  # avoid circular at module level

        conditions = ["guild_id = ?"]
        params: list[str] = [str(guild_id)]
        if game:
            conditions.append("game = ?")
            params.append(game)

        cursor = await self.connection.execute(
            f"SELECT DISTINCT game, iteration FROM user_scores "
            f"WHERE {' AND '.join(conditions)}",
            params,
        )
        pairs = await cursor.fetchall()

        latest: dict[str, str] = {}
        for pair_game, iteration in pairs:
            if (
                pair_game not in latest
                or _iteration_key(iteration) > _iteration_key(latest[pair_game])
            ):
                latest[pair_game] = iteration

        if not latest:
            return []

        placeholders = ", ".join("(?, ?)" for _ in latest)
        rows = await self.connection.execute(
            f"SELECT user_id, user_name, game, iteration, day, score, meta "
            f"FROM user_scores WHERE guild_id = ? "
            f"AND (game, iteration) IN ({placeholders}) ORDER BY game",
            [str(guild_id)] + [item for pair in latest.items() for item in pair],
        )
        results = await rows.fetchall()
        return [
            ScoreRecord(
                user_id=int(row[0]),
                user_name=row[1],
                game=row[2],
                iteration=row[3],
                day=row[4],
                score=row[5],
                meta=json.loads(row[6]) if row[6] else None,
            )
            for row in results
        ]
