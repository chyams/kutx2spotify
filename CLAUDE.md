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
tests/              # Test files
```

## Conventions

- Virtual environment: `~/venvs/kutx2spotify` (not .venv)
- 96% test coverage required
- Strict mypy typing
- ruff for formatting and linting
