#!/usr/bin/env python3
"""Regenerate the README's "Supported games" table from the discovered parsers.

The parsers/ directory auto-discovers a `ScoreParser` per game; this tool keeps
the README table (`| Game | Play |`) in sync with whatever parsers exist.

Usage:
    python update_readme_games.py          # rewrite the table in place
    python update_readme_games.py --check  # verify it's up to date (exit 1 if not)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.registry import build_game_table_markdown  # noqa: E402

README_PATH = PROJECT_ROOT / "README.md"
SECTION_HEADING = "# Supported games"

_HEADER_RE = re.compile(r"^\|\s*Game\s*\|\s*Play\s*\|$")
_SEPARATOR_RE = re.compile(r"^\|[-| :]+\|$")


def regenerate() -> str:
    """Return README content with the Supported games table refreshed."""
    text = README_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

    try:
        heading = next(i for i, line in enumerate(lines) if line == SECTION_HEADING)
    except StopIteration:
        raise SystemExit(f"README.md has no '{SECTION_HEADING}' section") from None

    # A "| Game | Play |" header followed by its separator row marks the table.
    try:
        header_index = next(
            i
            for i in range(heading + 1, len(lines) - 1)
            if _HEADER_RE.match(lines[i]) and _SEPARATOR_RE.match(lines[i + 1])
        )
    except StopIteration:
        raise SystemExit(
            f"Could not find the '| Game | Play |' table in the '{SECTION_HEADING}' section"
        ) from None

    # The table runs while consecutive lines keep starting with '|'.
    stop = header_index + 2
    while stop < len(lines) and lines[stop].startswith("|"):
        stop += 1

    new_table = build_game_table_markdown().splitlines()
    updated = lines[:header_index] + new_table + lines[stop:]
    return "\n".join(updated).rstrip("\n") + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify the table is up to date and exit 1 if it isn't",
    )
    args = ap.parse_args()

    new = regenerate()
    current = README_PATH.read_text(encoding="utf-8")

    if args.check:
        if new != current:
            print(
                "README Supported games table is out of date — run "
                "`python update_readme_games.py` to regenerate it."
            )
            raise SystemExit(1)
        print("README Supported games table is up to date.")
        return

    if new == current:
        print("README Supported games table is already up to date.")
        return
    README_PATH.write_text(new, encoding="utf-8")
    print(f"Updated {README_PATH}")


if __name__ == "__main__":
    main()