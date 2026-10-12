"""Bot-wide timezone handling

Every part of trivial that needs today's date, yesterday's date, the current
clock time, or the calendar day a message/share belongs to goes through this
module.

``TIMEZONE`` sets the *default* IANA timezone name for the whole bot, e.g.
``America/New_York`` or ``Asia/Tokyo``; it defaults to ``UTC``. Individual
servers can override it with the ``/timezone`` command and fall back to this
default when they haven't. Every helper below takes an optional ``tz`` (a
:class:`~zoneinfo.ZoneInfo`): pass a server's resolved timezone to get that
server's local dates, or leave it out to use the bot default.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import AbstractSet
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"

_INVALID_TZ = (
    "Invalid timezone {name!r} - expected an IANA timezone name "
    "(e.g. 'UTC', 'America/New_York', 'Europe/London'). "
    "See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones."
)


def get_timezone(name: str | None) -> ZoneInfo:
    """Resolve an IANA timezone *name* to a :class:`ZoneInfo`.

    ``None`` or a blank name yields the bot's default timezone. Raises
    :class:`ValueError` for an unknown timezone so callers can validate input
    before storing it.
    """
    if name is None or not name.strip():
        return TARGET_TZ
    candidate = name.strip()
    try:
        return ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(_INVALID_TZ.format(name=candidate)) from exc


def _load_timezone() -> ZoneInfo:
    name = os.getenv("TIMEZONE", default=DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    return get_timezone(name)


TARGET_TZ: ZoneInfo = _load_timezone()


def _zone(tz: ZoneInfo | None) -> ZoneInfo:
    """The given timezone, or the bot default when unset."""
    return tz or TARGET_TZ


def bot_tz() -> ZoneInfo:
    """The bot's default timezone (the ``TIMEZONE`` env var / ``UTC``)."""
    return TARGET_TZ


def now(tz: ZoneInfo | None = None) -> datetime:
    """The current moment in *tz* (or the bot default). Timezone-aware."""
    return datetime.now(_zone(tz))


def as_bot_tz(value: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Convert *value* to *tz* (or the bot default).

    Naive datetimes are assumed to be UTC (discord.py's default for
    timestamps).
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_zone(tz))


def today_str(tz: ZoneInfo | None = None) -> str:
    """Today's date as ``YYYY-MM-DD`` in *tz* (or the bot default)."""
    return now(tz).strftime("%Y-%m-%d")


def yesterday_str(tz: ZoneInfo | None = None) -> str:
    """Yesterday's date as ``YYYY-MM-DD`` in *tz* (or the bot default)."""
    return (now(tz) - timedelta(days=1)).strftime("%Y-%m-%d")


def time_str(tz: ZoneInfo | None = None) -> str:
    """The current clock time as ``HH:MM`` in *tz* (or the bot default)."""
    return now(tz).strftime("%H:%M")


def active_streak(days: AbstractSet[str], through: str) -> int:
    """How many consecutive calendar days in *days* end on *through*.
    """
    cursor = date.fromisoformat(through)
    count = 0
    while cursor.isoformat() in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def day_string(value: datetime, tz: ZoneInfo | None = None) -> str:
    """The calendar date *value* falls on in *tz*, ``YYYY-MM-DD``."""
    return as_bot_tz(value, tz).strftime("%Y-%m-%d")


def now_label(tz: ZoneInfo | None = None) -> str:
    """Short human-friendly date label, e.g. ``2026-09-19 (America/New_York)``."""
    zone = _zone(tz)
    return f"{today_str(zone)} ({zone})"
