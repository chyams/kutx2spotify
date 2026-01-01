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
tests/              # Test files
```

## Cache Locations

- KUTX playlists: `~/.cache/kutx2spotify/kutx/YYYY-MM-DD.json`
- Match resolutions: `~/.cache/kutx2spotify/resolutions.json`

## Conventions

- Virtual environment: `~/venvs/kutx2spotify` (not .venv)
- 96% test coverage required
- Strict mypy typing
- ruff for formatting and linting
