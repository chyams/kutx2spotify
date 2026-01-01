# kutx2spotify

## Purpose

KUTX to Spotify integration.

## Tech Stack

- Python 3.11+
- ruff (formatting + linting)
- mypy (type checking)
- pytest (testing)

## Development Setup

```bash
source ~/venvs/kutx2spotify/bin/activate
just dev        # Install dependencies
just hooks      # Install git hooks
just test       # Run tests
just check-all  # Run all checks
```

## Project Structure

```
src/kutx2spotify/   # Main package
  models.py         # Data models (Song, SpotifyTrack, Match, etc.)
  kutx.py           # KUTX API client
  cache.py          # Caching layer (KUTX playlists, match resolutions)
  spotify.py        # Spotify API client
  matcher.py        # Song matching engine
  cli.py            # Click CLI interface
  output.py         # Rich output formatting
tests/              # Test files
```

## KUTX API

NPR Composer API: `https://api.composer.nprstations.org/v1/widget/50ef24ebe1c8a1369593d032/day`

Response structure (playlists nested in program blocks):
```json
{
  "onToday": [
    { "playlist": [ { "trackName": "...", "artistName": "...", ... } ] },
    { "playlist": [ ... ] }
  ]
}
```

## Cache Locations

- KUTX playlists: `~/.cache/kutx2spotify/kutx/YYYY-MM-DD.json`
- Match resolutions: `~/.cache/kutx2spotify/resolutions.json`

## Matching Algorithm

1. Check resolution cache first (user-stored decisions)
2. Exact match: search with album, verify album matches
3. Album fallback: search without album if exact not found
4. Duration filter: prefer tracks within +/- 10 seconds
5. Popularity tiebreaker: pick most popular if multiple matches

## Conventions

- Virtual environment: `~/venvs/kutx2spotify` (not .venv)
- 96% test coverage required
- Strict mypy typing
- ruff for formatting and linting
