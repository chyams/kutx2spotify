"""Tests for the caching layer."""

import json
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from kutx2spotify.cache import (
    DEFAULT_KUTX_TTL_HOURS,
    KUTXCache,
    Resolution,
    ResolutionCache,
    _dict_to_song,
    _get_cache_dir,
    _make_resolution_key,
    _song_to_dict,
)
from kutx2spotify.models import Song


@pytest.fixture
def temp_cache_dir() -> Path:
    """Create a temporary directory for cache tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_song() -> Song:
    """Create a sample song for testing."""
    return Song(
        title="We Can Work It Out",
        artist="Stevie Wonder",
        album="The Complete Motown Singles",
        duration_ms=180000,
        played_at=datetime(2024, 1, 15, 14, 30, 0),
    )


@pytest.fixture
def sample_songs() -> list[Song]:
    """Create a list of sample songs for testing."""
    return [
        Song(
            title="Song One",
            artist="Artist A",
            album="Album 1",
            duration_ms=200000,
            played_at=datetime(2024, 1, 15, 10, 0, 0),
        ),
        Song(
            title="Song Two",
            artist="Artist B",
            album="Album 2",
            duration_ms=300000,
            played_at=datetime(2024, 1, 15, 11, 0, 0),
        ),
    ]


class TestSongSerialization:
    """Tests for song serialization helpers."""

    def test_song_to_dict(self, sample_song: Song) -> None:
        """Test converting a Song to a dict."""
        result = _song_to_dict(sample_song)

        assert result["title"] == "We Can Work It Out"
        assert result["artist"] == "Stevie Wonder"
        assert result["album"] == "The Complete Motown Singles"
        assert result["duration_ms"] == 180000
        assert result["played_at"] == "2024-01-15T14:30:00"

    def test_dict_to_song(self) -> None:
        """Test converting a dict back to a Song."""
        data = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration_ms": 240000,
            "played_at": "2024-01-15T12:00:00",
        }

        result = _dict_to_song(data)

        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.album == "Test Album"
        assert result.duration_ms == 240000
        assert result.played_at == datetime(2024, 1, 15, 12, 0, 0)

    def test_roundtrip(self, sample_song: Song) -> None:
        """Test that song survives serialization roundtrip."""
        data = _song_to_dict(sample_song)
        result = _dict_to_song(data)
        assert result == sample_song


class TestGetCacheDir:
    """Tests for _get_cache_dir helper."""

    def test_creates_directory(self, temp_cache_dir: Path) -> None:
        """Test that cache directory is created."""
        with patch("kutx2spotify.cache.DEFAULT_CACHE_DIR", temp_cache_dir / "cache"):
            result = _get_cache_dir()
            assert result.exists()
            assert result.is_dir()


class TestKUTXCache:
    """Tests for KUTXCache class."""

    def test_init_creates_directory(self, temp_cache_dir: Path) -> None:
        """Test that init creates cache directory."""
        cache_dir = temp_cache_dir / "kutx"
        cache = KUTXCache(cache_dir=cache_dir)

        assert cache.cache_dir.exists()
        assert cache.ttl_hours == DEFAULT_KUTX_TTL_HOURS

    def test_init_default_ttl(self, temp_cache_dir: Path) -> None:
        """Test default TTL value."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        assert cache.ttl_hours == 24

    def test_init_custom_ttl(self, temp_cache_dir: Path) -> None:
        """Test custom TTL value."""
        cache = KUTXCache(cache_dir=temp_cache_dir, ttl_hours=12)
        assert cache.ttl_hours == 12

    def test_get_miss(self, temp_cache_dir: Path) -> None:
        """Test cache miss returns None."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        date = datetime(2024, 1, 15)

        result = cache.get(date)

        assert result is None

    def test_set_and_get(self, temp_cache_dir: Path, sample_songs: list[Song]) -> None:
        """Test setting and getting cached data."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        date = datetime(2024, 1, 15)

        cache.set(date, sample_songs)
        result = cache.get(date)

        assert result is not None
        assert len(result) == 2
        assert result[0].title == "Song One"
        assert result[1].title == "Song Two"

    def test_cache_path_format(self, temp_cache_dir: Path) -> None:
        """Test cache file path format."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        date = datetime(2024, 1, 15)

        path = cache._cache_path(date)

        assert path == temp_cache_dir / "2024-01-15.json"

    def test_get_expired(self, temp_cache_dir: Path, sample_songs: list[Song]) -> None:
        """Test that expired cache returns None."""
        cache = KUTXCache(cache_dir=temp_cache_dir, ttl_hours=1)
        date = datetime(2024, 1, 15)

        cache.set(date, sample_songs)

        # Mock file modification time to be old
        path = cache._cache_path(date)
        old_time = time.time() - (2 * 3600)  # 2 hours ago
        import os

        os.utime(path, (old_time, old_time))

        result = cache.get(date)
        assert result is None

    def test_get_not_expired(
        self, temp_cache_dir: Path, sample_songs: list[Song]
    ) -> None:
        """Test that non-expired cache returns data."""
        cache = KUTXCache(cache_dir=temp_cache_dir, ttl_hours=24)
        date = datetime(2024, 1, 15)

        cache.set(date, sample_songs)
        result = cache.get(date)

        assert result is not None
        assert len(result) == 2

    def test_get_invalid_json(self, temp_cache_dir: Path) -> None:
        """Test that invalid JSON returns None."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        date = datetime(2024, 1, 15)

        # Write invalid JSON
        path = cache._cache_path(date)
        path.write_text("not valid json")

        result = cache.get(date)
        assert result is None

    def test_get_invalid_data(self, temp_cache_dir: Path) -> None:
        """Test that invalid data structure returns None."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        date = datetime(2024, 1, 15)

        # Write JSON with missing keys
        path = cache._cache_path(date)
        path.write_text('[{"invalid": "data"}]')

        result = cache.get(date)
        assert result is None

    def test_clear_existing(
        self, temp_cache_dir: Path, sample_songs: list[Song]
    ) -> None:
        """Test clearing existing cache."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        date = datetime(2024, 1, 15)

        cache.set(date, sample_songs)
        result = cache.clear(date)

        assert result is True
        assert cache.get(date) is None

    def test_clear_nonexistent(self, temp_cache_dir: Path) -> None:
        """Test clearing non-existent cache."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        date = datetime(2024, 1, 15)

        result = cache.clear(date)

        assert result is False

    def test_clear_all(self, temp_cache_dir: Path, sample_songs: list[Song]) -> None:
        """Test clearing all cache files."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        dates = [
            datetime(2024, 1, 15),
            datetime(2024, 1, 16),
            datetime(2024, 1, 17),
        ]

        for date in dates:
            cache.set(date, sample_songs)

        count = cache.clear_all()

        assert count == 3
        for date in dates:
            assert cache.get(date) is None

    def test_clear_all_empty(self, temp_cache_dir: Path) -> None:
        """Test clearing empty cache."""
        cache = KUTXCache(cache_dir=temp_cache_dir)
        count = cache.clear_all()
        assert count == 0


class TestResolution:
    """Tests for Resolution dataclass."""

    def test_create_with_all_fields(self) -> None:
        """Test creating a resolution with all fields."""
        resolution = Resolution(
            spotify_uri="spotify:track:xxx",
            resolved_album="Signed, Sealed & Delivered",
            note="Original album not on Spotify",
        )

        assert resolution.spotify_uri == "spotify:track:xxx"
        assert resolution.resolved_album == "Signed, Sealed & Delivered"
        assert resolution.note == "Original album not on Spotify"

    def test_create_with_defaults(self) -> None:
        """Test creating a resolution with defaults."""
        resolution = Resolution(
            spotify_uri="spotify:track:yyy",
            resolved_album="Some Album",
        )

        assert resolution.note == ""


class TestMakeResolutionKey:
    """Tests for _make_resolution_key helper."""

    def test_creates_lowercase_key(self, sample_song: Song) -> None:
        """Test that key is lowercase."""
        key = _make_resolution_key(sample_song)

        assert key == "we can work it out|stevie wonder|the complete motown singles"
        assert key == key.lower()

    def test_key_format(self) -> None:
        """Test key format with pipe separators."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=100,
            played_at=datetime.now(),
        )

        key = _make_resolution_key(song)

        assert key == "test|artist|album"
        assert key.count("|") == 2


class TestResolutionCache:
    """Tests for ResolutionCache class."""

    def test_init_with_path(self, temp_cache_dir: Path) -> None:
        """Test initialization with explicit path."""
        path = temp_cache_dir / "resolutions.json"
        cache = ResolutionCache(cache_path=path)

        assert cache.cache_path == path

    def test_has_miss(self, temp_cache_dir: Path, sample_song: Song) -> None:
        """Test has() returns False for missing song."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")

        assert cache.has(sample_song) is False

    def test_get_miss(self, temp_cache_dir: Path, sample_song: Song) -> None:
        """Test get() returns None for missing song."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")

        result = cache.get(sample_song)

        assert result is None

    def test_set_and_get(self, temp_cache_dir: Path, sample_song: Song) -> None:
        """Test setting and getting a resolution."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")
        resolution = Resolution(
            spotify_uri="spotify:track:abc123",
            resolved_album="Signed, Sealed & Delivered",
            note="Found alternate album",
        )

        cache.set(sample_song, resolution)
        result = cache.get(sample_song)

        assert result is not None
        assert result.spotify_uri == "spotify:track:abc123"
        assert result.resolved_album == "Signed, Sealed & Delivered"
        assert result.note == "Found alternate album"

    def test_set_and_has(self, temp_cache_dir: Path, sample_song: Song) -> None:
        """Test has() returns True after setting."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")
        resolution = Resolution(
            spotify_uri="spotify:track:xyz",
            resolved_album="Album",
        )

        cache.set(sample_song, resolution)

        assert cache.has(sample_song) is True

    def test_case_insensitive(self, temp_cache_dir: Path) -> None:
        """Test that lookups are case-insensitive."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")
        resolution = Resolution(
            spotify_uri="spotify:track:123",
            resolved_album="Album",
        )

        song1 = Song(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_ms=100,
            played_at=datetime.now(),
        )
        song2 = Song(
            title="TEST SONG",
            artist="TEST ARTIST",
            album="TEST ALBUM",
            duration_ms=100,
            played_at=datetime.now(),
        )

        cache.set(song1, resolution)

        # Should find with different case
        result = cache.get(song2)
        assert result is not None
        assert result.spotify_uri == "spotify:track:123"

    def test_persistence(self, temp_cache_dir: Path, sample_song: Song) -> None:
        """Test that resolutions persist across cache instances."""
        path = temp_cache_dir / "res.json"
        resolution = Resolution(
            spotify_uri="spotify:track:persist",
            resolved_album="Persisted Album",
        )

        # Set with first instance
        cache1 = ResolutionCache(cache_path=path)
        cache1.set(sample_song, resolution)

        # Get with second instance
        cache2 = ResolutionCache(cache_path=path)
        result = cache2.get(sample_song)

        assert result is not None
        assert result.spotify_uri == "spotify:track:persist"

    def test_remove_existing(self, temp_cache_dir: Path, sample_song: Song) -> None:
        """Test removing an existing resolution."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")
        resolution = Resolution(
            spotify_uri="spotify:track:remove",
            resolved_album="Album",
        )

        cache.set(sample_song, resolution)
        result = cache.remove(sample_song)

        assert result is True
        assert cache.has(sample_song) is False

    def test_remove_nonexistent(self, temp_cache_dir: Path, sample_song: Song) -> None:
        """Test removing a non-existent resolution."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")

        result = cache.remove(sample_song)

        assert result is False

    def test_clear(self, temp_cache_dir: Path) -> None:
        """Test clearing all resolutions."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")
        songs = [
            Song(
                title=f"Song {i}",
                artist="Artist",
                album="Album",
                duration_ms=100,
                played_at=datetime.now(),
            )
            for i in range(3)
        ]

        for song in songs:
            cache.set(
                song,
                Resolution(spotify_uri=f"uri:{song.title}", resolved_album="Album"),
            )

        count = cache.clear()

        assert count == 3
        for song in songs:
            assert cache.has(song) is False

    def test_count(self, temp_cache_dir: Path) -> None:
        """Test counting resolutions."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")

        assert cache.count() == 0

        for i in range(5):
            song = Song(
                title=f"Song {i}",
                artist="Artist",
                album="Album",
                duration_ms=100,
                played_at=datetime.now(),
            )
            cache.set(
                song,
                Resolution(spotify_uri=f"uri:{i}", resolved_album="Album"),
            )

        assert cache.count() == 5

    def test_load_invalid_json(self, temp_cache_dir: Path) -> None:
        """Test loading invalid JSON file."""
        path = temp_cache_dir / "res.json"
        path.write_text("not valid json")

        cache = ResolutionCache(cache_path=path)

        assert cache.count() == 0

    def test_get_with_missing_note(self, temp_cache_dir: Path) -> None:
        """Test getting a resolution that has no note field."""
        path = temp_cache_dir / "res.json"
        # Write data without 'note' field
        data = {
            "song|artist|album": {
                "spotify_uri": "spotify:track:xyz",
                "resolved_album": "Album",
            }
        }
        with path.open("w") as f:
            json.dump(data, f)

        cache = ResolutionCache(cache_path=path)
        song = Song(
            title="Song",
            artist="Artist",
            album="Album",
            duration_ms=100,
            played_at=datetime.now(),
        )

        result = cache.get(song)

        assert result is not None
        assert result.note == ""

    def test_update_existing(self, temp_cache_dir: Path, sample_song: Song) -> None:
        """Test updating an existing resolution."""
        cache = ResolutionCache(cache_path=temp_cache_dir / "res.json")

        cache.set(
            sample_song,
            Resolution(
                spotify_uri="spotify:track:first",
                resolved_album="First Album",
            ),
        )
        cache.set(
            sample_song,
            Resolution(
                spotify_uri="spotify:track:second",
                resolved_album="Second Album",
            ),
        )

        result = cache.get(sample_song)
        assert result is not None
        assert result.spotify_uri == "spotify:track:second"
        assert cache.count() == 1
