"""Browser automation utilities for Spotify integration."""

import asyncio
import json
import random
from pathlib import Path


def get_cookie_path() -> Path:
    """Get path to cookie storage file."""
    cache_dir = Path.home() / ".cache" / "kutx2spotify"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "spotify_cookies.json"


def save_cookies(cookies: list[dict[str, object]]) -> None:
    """Save cookies to disk."""
    path = get_cookie_path()
    path.write_text(json.dumps(cookies, indent=2))


def load_cookies() -> list[dict[str, object]] | None:
    """Load cookies from disk, return None if not found."""
    path = get_cookie_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data
        return None
    except (json.JSONDecodeError, OSError):
        return None


def clear_cookies() -> None:
    """Delete saved cookies."""
    path = get_cookie_path()
    if path.exists():
        path.unlink()


async def human_delay(min_ms: int = 1000, max_ms: int = 2000) -> None:
    """Random delay to mimic human behavior.

    Args:
        min_ms: Minimum delay in milliseconds.
        max_ms: Maximum delay in milliseconds.
    """
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)
