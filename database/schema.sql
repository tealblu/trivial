CREATE TABLE IF NOT EXISTS `score_channels` (
  `server_id` varchar(20) NOT NULL,
  `channel_id` varchar(20) NOT NULL,
  PRIMARY KEY (`server_id`)
);

-- One row per guild: daily reminder configuration.
-- `reminder_time` is "HH:MM" (24-hour) in the server's timezone (see
-- `guild_timezones`; falls back to the TIMEZONE env var, UTC by default).
-- `last_fired` stores the last date (YYYY-MM-DD, server's timezone) the
-- reminder was sent so it doesn't re-fire that day.
CREATE TABLE IF NOT EXISTS `daily_reminders` (
  `server_id`     varchar(20) NOT NULL,
  `enabled`       int         NOT NULL DEFAULT 0,
  `reminder_time` varchar(5)  NOT NULL DEFAULT '09:00',
  `last_fired`    varchar(10) NULL,
  `updated_at`    timestamp   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`server_id`)
);

-- One row per guild that overrides the bot's default timezone. `timezone` is
-- an IANA name (e.g. "America/New_York"). Guilds without a row here use the
-- bot default (the TIMEZONE env var; UTC when unset).
CREATE TABLE IF NOT EXISTS `guild_timezones` (
  `server_id`  varchar(20) NOT NULL,
  `timezone`   varchar(64) NOT NULL,
  `updated_at` timestamp   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`server_id`)
);

-- One row per (guild, user, game, iteration): many users x many games,
-- one score per puzzle. Re-posting the same puzzle overwrites the row.
-- `iteration` is the game's own puzzle identifier — Wordle's puzzle number
-- ("1925"), Krillion's "#64", Metazooa's "#1153", or, for games whose share
-- labels the puzzle by date (dialed, maptap), the share's own date as
-- YYYY-MM-DD ("2026-09-18"). Keying on the iteration instead of the log date
-- keeps boards consistent even when games reset or iterate at different
-- times than the bot's calendar.
-- `score` is REAL so decimal scores (e.g. dialed's 40.49/50) store exactly;
-- most games still write whole numbers.
-- `day` is the date the score was LOGGED (YYYY-MM-DD, the server's timezone;
-- see `guild_timezones`) and exists purely for reference — nothing is keyed
-- or ranked off it.
CREATE TABLE IF NOT EXISTS `user_scores` (
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

-- Leaderboard queries filter on (guild_id, game, iteration) to pick each
-- game's latest iteration; the reminder's play-day queries filter on
-- (guild_id, day). Applied on every startup via executescript, so existing
-- databases get them too.
CREATE INDEX IF NOT EXISTS `idx_user_scores_guild_game_iteration`
  ON `user_scores` (`guild_id`, `game`, `iteration`);
CREATE INDEX IF NOT EXISTS `idx_user_scores_guild_day`
  ON `user_scores` (`guild_id`, `day`);
