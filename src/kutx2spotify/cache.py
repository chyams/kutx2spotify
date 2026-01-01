"""Caching layer for KUTX playlist data and match resolutions."""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from kutx2spotify.models import Song

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "kutx2spotify"
DEFAULT_KUTX_TTL_HOURS = 24


def _get_cache_dir() -> Path:
    """Get the cache directory, creating it if needed."""
    cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _song_to_dict(song: Song) -> dict[str, Any]:
    """Convert a Song to a JSON-serializable dict."""
    return {
        "title": song.title,
        "artist": song.artist,
        "album": song.album,
        "duration_ms": song.duration_ms,
        "played_at": song.played_at.isoformat(),
    }


def _dict_to_song(data: dict[str, Any]) -> Song:
    """Convert a dict back to a Song."""
    return Song(
        title=data["title"],
        artist=data["artist"],
        album=data["album"],
        duration_ms=data["duration_ms"],
        played_at=datetime.fromisoformat(data["played_at"]),
    )


class KUTXCache:
    """Cache for KUTX playlist data.

    Stores playlist data by date in JSON files.
    Default location: ~/.cache/kutx2spotify/kutx/YYYY-MM-DD.json
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_hours: int = DEFAULT_KUTX_TTL_HOURS,
    ) -> None:
        """Initialize the KUTX cache.

        Args:
            cache_dir: Directory for cache files. Defaults to ~/.cache/kutx2spotify/kutx/
            ttl_hours: Time-to-live in hours for cached data. Defaults to 24.
        """
        if cache_dir is None:
            cache_dir = _get_cache_dir() / "kutx"
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, date: datetime) -> Path:
        """Get the cache file path for a date."""
        return self.cache_dir / f"{date.strftime('%Y-%m-%d')}.json"

    def _is_expired(self, path: Path) -> bool:
        """Check if a cache file has expired based on TTL."""
        if not path.exists():
            return True
        mtime = path.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        return age_hours > self.ttl_hours

    def get(self, date: datetime) -> list[Song] | None:
        """Get cached playlist for a date.

        Args:
            date: The date to get cached data for.

        Returns:
            List of songs if cache hit and not expired, None otherwise.
        """
        path = self._cache_path(date)

        if not path.exists():
            return None

        if self._is_expired(path):
            return None

        try:
            with path.open("r") as f:
                data = json.load(f)
            return [_dict_to_song(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            return None

    def set(self, date: datetime, songs: list[Song]) -> None:
        """Cache playlist data for a date.

        Args:
            date: The date to cache data for.
            songs: List of songs to cache.
        """
        path = self._cache_path(date)
        data = [_song_to_dict(s) for s in songs]
        with path.open("w") as f:
            json.dump(data, f)

    def clear(self, date: datetime) -> bool:
        """Clear cached data for a specific date.

        Args:
            date: The date to clear cache for.

        Returns:
            True if cache was cleared, False if no cache existed.
        """
        path = self._cache_path(date)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear_all(self) -> int:
        """Clear all cached KUTX data.

        Returns:
            Number of cache files deleted.
        """
        count = 0
        for path in self.cache_dir.glob("*.json"):
            path.unlink()
            count += 1
        return count


@dataclass(frozen=True)
class Resolution:
    """A stored resolution for a song match."""

    spotify_uri: str
    resolved_album: str
    note: str = ""


def _make_resolution_key(song: Song) -> str:
    """Create a case-insensitive key for a song.

    Key format: title|artist|album (all lowercase)
    """
    return f"{song.title}|{song.artist}|{song.album}".lower()


class ResolutionCache:
    """Cache for match resolutions.

    Stores user decisions about song-to-track matches.
    Default location: ~/.cache/kutx2spotify/resolutions.json
    """

    def __init__(self, cache_path: Path | None = None) -> None:
        """Initialize the resolution cache.

        Args:
            cache_path: Path to the cache file.
                       Defaults to ~/.cache/kutx2spotify/resolutions.json
        """
        if cache_path is None:
            cache_path = _get_cache_dir() / "resolutions.json"
        self.cache_path = cache_path
        self._data: dict[str, dict[str, Any]] | None = None

    def _load(self) -> dict[str, dict[str, Any]]:
        """Load the resolution cache from disk."""
        if self._data is not None:
            return self._data

        if not self.cache_path.exists():
            self._data = {}
            return self._data

        try:
            with self.cache_path.open("r") as f:
                self._data = json.load(f)
        except json.JSONDecodeError:
            self._data = {}

        return self._data

    def _save(self) -> None:
        """Save the resolution cache to disk."""
        if self._data is None:
            return

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("w") as f:
            json.dump(self._data, f, indent=2)

    def has(self, song: Song) -> bool:
        """Check if a resolution exists for a song.

        Args:
            song: The song to check.

        Returns:
            True if a resolution exists.
        """
        key = _make_resolution_key(song)
        return key in self._load()

    def get(self, song: Song) -> Resolution | None:
        """Get a stored resolution for a song.

        Args:
            song: The song to look up.

        Returns:
            Resolution if found, None otherwise.
        """
        key = _make_resolution_key(song)
        data = self._load()

        if key not in data:
            return None

        entry = data[key]
        return Resolution(
            spotify_uri=entry["spotify_uri"],
            resolved_album=entry["resolved_album"],
            note=entry.get("note", ""),
        )

    def set(self, song: Song, resolution: Resolution) -> None:
        """Store a resolution for a song.

        Args:
            song: The song to store resolution for.
            resolution: The resolution to store.
        """
        key = _make_resolution_key(song)
        data = self._load()
        data[key] = {
            "spotify_uri": resolution.spotify_uri,
            "resolved_album": resolution.resolved_album,
            "note": resolution.note,
        }
        self._save()

    def remove(self, song: Song) -> bool:
        """Remove a resolution for a song.

        Args:
            song: The song to remove resolution for.

        Returns:
            True if resolution was removed, False if not found.
        """
        key = _make_resolution_key(song)
        data = self._load()

        if key not in data:
            return False

        del data[key]
        self._save()
        return True

    def clear(self) -> int:
        """Clear all stored resolutions.

        Returns:
            Number of resolutions cleared.
        """
        data = self._load()
        count = len(data)
        self._data = {}
        self._save()
        return count

    def count(self) -> int:
        """Get the number of stored resolutions.

        Returns:
            Number of resolutions.
        """
        return len(self._load())
