<p align="center">
  <img src="resources/triviala.png" alt="Trivial logo" width="150">
</p>

**trivial** is a Discord bot that automatically tracks daily game scores from chat
messages. When a user posts their score, trivial remembers it. Trivial can show scores for specified days, leaderboards with various metrics, send daily reminder messages so you don't forget to play, track streaks, and more!

# Supported games

| Game | Play |
|------|------|
| Airportguessr | [planespottle.net](https://planespottle.net/airportguessr) |
| Catfishing | [catfishing.net](https://catfishing.net) |
| Dialed | [dialed.gg](https://dialed.gg/color) |
| Flagle | [flagle-game.com](https://flagle-game.com/) |
| Geosportle | [geosportle.app](https://geosportle.app) |
| Gundle | [playgundle.com](https://playgundle.com/) |
| Krillion | [krillion.io](https://krillion.io) |
| Maptap | [maptap.gg](https://www.maptap.gg) |
| Metaflora | [flora.metazooa.com](https://flora.metazooa.com) |
| Metazooa | [metazooa.com](https://metazooa.com) |
| Planespottle | [planespottle.net](https://planespottle.net) |
| Poople | [poople.io](https://poople.io) |
| Songless | [less.gg](https://less.gg/songless) |
| Wordle | [nytimes.com](https://www.nytimes.com/games/wordle/index.html) |

Every supported game is also listed in Discord with `!/games`.

# Add trivial to your server

1. [Add trivial to your server](https://discord.com/oauth2/authorize?client_id=1550155002809557002&permissions=3088&integration_type=0&scope=applications.commands+bot).
2. Run `/scorechannel set #channel` to choose the channel trivial watches for
   score messages (requires the **Manage Server** permission in that server).
   To watch a thread instead, open it and run `/bind` (or `!bind`) there.
3. (Optional) Set the server's timezone so scores land on the right days and
   the daily reminder fires when you expect:
   ```
   /timezone set America/New_York
   ```
   Without an override, every server uses the bot's default timezone (UTC).

That's it! Drop a game result
into the monitored channel or thread and trivial records it; use `/scores` and
`/leaderboard` to see how everyone is doing.

# Self-hosting (advanced)

Prefer to run your own copy of trivial instead of using a hosted one? You'll
need a Discord application of your own:

0. Set up a new bot in the [discord developer portal](https://discord.com/developers/home).

1. Copy `.env.example` to `.env` and fill in your bot token and prefix:
   ```
   TOKEN=your-bot-token
   PREFIX=!
   ```
2. (Optional) Set the bot's **default** timezone — an IANA name like
   `America/New_York` or `Asia/Tokyo`:
   ```
   TIMEZONE=America/New_York
   ```
   This is the fallback for every server that hasn't set its own with
   `/timezone`. When unset the bot uses UTC, which keeps every prior behaviour
   unchanged.
3. Install dependencies:
   ```
   python -m pip install -r requirements.txt
   ```
4. Run trivial:
   ```
   python bot.py
   ```

> **Required intents:** enable **Message Content Intent** (reads score
> messages) and **Server Members Intent** (resolves current server nicknames)
> under *Bot → Privileged Gateway Intents* in the [Discord Developer
> Portal](https://discord.com/developers/applications). Without the members
> intent, player names may not be resolved correctly.

### Docker

```
docker compose up -d --build
```

### Deploy from GHCR

On a server with Docker:

```
GHCR_OWNER=your-github-user docker compose up -d
```

Make sure `.env` exists with at least `TOKEN` and `PREFIX`.

# Commands

| Command | Description |
|---------|-------------|
| `!/scores` | Each game's most recent iteration of scores, pooled across every server the players share (available to everyone) |
| `!/scores wordle` | Wordle's most recent iteration of scores, pooled across servers (available to everyone) |
| `!/scores 2026-10-11` | Every game's scores logged on that date, pooled across servers (available to everyone) |
| `!/scores wordle 2026-10-11` | Wordle's scores logged on that date; a game that iterated mid-day shows each iteration (available to everyone) |
| `!/leaderboard` | Top 3 players for each game by average score, all time, pooled across servers (available to everyone) |
| `!/leaderboard wordle` | Top 3 Wordle players by average score, all time, pooled across servers (available to everyone) |
| `!/leaderboard wordle top` | Top 3 Wordle players by best score, all time (available to everyone) |
| `!/leaderboard wordle wins` | Top 3 Wordle players by first-place finishes, all time (available to everyone) |
| `!/leaderboard wordle count` | Top 3 Wordle players by games played, all time (available to everyone) |
| `!/games` | List every supported game with a link to play (available to everyone) |
| `!/bind` | Bind trivial to the channel or thread the command is used in (admins only) |
| `!/scorechannel set #channel` | Set the channel or thread trivial monitors for scores (admins only) |
| `!/scorechannel remove` | Stop monitoring scores in this server (admins only) |
| `!/scorechannel show` | Show the currently monitored score channel or thread (admins only) |
| `!/nuke confirm` | Permanently delete this server's recorded scores (admins only; keeps channel/reminder settings) |
| `!/backfill` | Scan the score channel or thread's history and record score messages (admins only; `!/backfill 1000` scans more, `0` = all history) |
| `!/dailyreminder enable` | Enable the daily games reminder (admins only; posts to the score channel or thread) |
| `!/dailyreminder disable` | Disable the daily games reminder (admins only) |
| `!/dailyreminder time 09:00` | Set the reminder time, 24-hour, in the server's timezone (admins only) |
| `!/dailyreminder show` | Show the current reminder settings (admins only) |
| `!/dailyreminder test` | Preview the daily reminder (plus latest scores and players) in this channel (admins only) |
| `!/timezone set America/New_York` | Set this server's timezone (admins only) |
| `!/timezone reset` | Go back to the bot's default timezone (admins only) |
| `!/timezone show` | Show this server's current timezone (admins only) |
| `!/sync global` | Re-sync the slash command tree with Discord (bot owner only) |
| `!/unsync global` | Remove the bot's slash commands (bot owner only) |

Every command above works both as a slash command (`/scores`) and as a prefix command (`!scores`).

# Development notes


## Adding a new game

"Parsers" are used to extract the game's score from a message. Parsers are auto-discovered from the `parsers/` directory. Adding support for a new game is as simple as dropping in a new file that subclasses `ScoreParser`.

Scores are keyed by the game's own puzzle iteration. Every concrete parser must set `ScoreResponse.iteration`
to the puzzle identifier it reads from the share — the puzzle number (e.g.
Wordle's `1925`, Metazooa's `1153`) or, for games whose share labels the
puzzle by date (dialed, maptap), the share's own date as `YYYY-MM-DD`. The
parser file should also carry an `example_message` class attribute: a full
pasted share containing the iteration number/date, so the format (and its
iteration) stays documented and testable. The date a score was *logged* is
still recorded on each row for reference, but nothing is keyed or ranked off
it.

## Local testing

You can exercise the full parsing and score-recording pipeline without
deploying trivial:

```
# Single message
python local_tester.py -p "Wordle 1,234 4/6"

# Interactive REPL
python local_tester.py

# File of messages
python local_tester.py -f test_inputs.txt
```

Simulate different users with an `@Name:userid ::` prefix:

```
@Alice:1001 :: Wordle 1,234 4/6
@Bob:1002 :: Wordle 1,235 X/6
```

To also simulate a server nickname that differs from the user's global
name (the bot prefers the nickname everywhere — leaderboards, embeds):

```
@Captain:1001 :: Wordle 1,234 4/6                    # nickname == global name
@Captain~Alice:1001 :: Wordle 1,234 4/6              # nickname "Captain", global name "Alice"
```

Other flags:

```
python local_tester.py --list                          # Show discovered parsers
python local_tester.py --scores wordle                 # Latest iteration of wordle (same embed as !scores)
python local_tester.py --scores wordle --date 2026-10-11  # Wordle's scores logged that day
python local_tester.py --leaderboard wordle            # Top-3-per-game leaderboard (all time)
python local_tester.py --leaderboard wordle --metric top  # Rank by best score
python local_tester.py --leaderboard wordle --metric wins # Rank by first-place finishes
python local_tester.py -f inputs.txt --verbose
python local_tester.py -f inputs.txt --db out/test.db  # Custom DB path
```

## AI Disclosure

AI was used to generate the initial framework for this project, as well as some of the documentation. Only open-weight models were used for AI-generated content, run through open-source tooling.

## License

This project is licensed under the Apache License 2.0 — see [LICENSE.md](LICENSE.md)
for details.

## Credits

Built on the [Python Discord Bot Template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template)
by [kkrypt0nn](https://github.com/kkrypt0nn).
