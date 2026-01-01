"""Tests for browser automation utilities."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from kutx2spotify.browser import (
    clear_cookies,
    get_cookie_path,
    human_delay,
    load_cookies,
    save_cookies,
)


@pytest.fixture
def temp_cache_dir() -> Path:
    """Create a temporary directory for cache tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestGetCookiePath:
    """Tests for get_cookie_path function."""

    def test_returns_path_in_cache_dir(self, temp_cache_dir: Path) -> None:
        """Test that cookie path is in cache directory."""
        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            path = get_cookie_path()

            assert path.name == "spotify_cookies.json"
            assert path.parent.name == "kutx2spotify"

    def test_creates_cache_directory(self, temp_cache_dir: Path) -> None:
        """Test that cache directory is created if not exists."""
        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            path = get_cookie_path()

            assert path.parent.exists()
            assert path.parent.is_dir()


class TestSaveCookies:
    """Tests for save_cookies function."""

    def test_saves_cookies_to_file(self, temp_cache_dir: Path) -> None:
        """Test that cookies are saved to disk."""
        cookies = [
            {"name": "session", "value": "abc123", "domain": ".spotify.com"},
            {"name": "token", "value": "xyz789", "domain": ".spotify.com"},
        ]

        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            save_cookies(cookies)

            path = get_cookie_path()
            assert path.exists()

            saved_data = json.loads(path.read_text())
            assert len(saved_data) == 2
            assert saved_data[0]["name"] == "session"
            assert saved_data[1]["name"] == "token"

    def test_saves_empty_cookies(self, temp_cache_dir: Path) -> None:
        """Test that empty cookie list can be saved."""
        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            save_cookies([])

            path = get_cookie_path()
            assert path.exists()

            saved_data = json.loads(path.read_text())
            assert saved_data == []


class TestLoadCookies:
    """Tests for load_cookies function."""

    def test_loads_saved_cookies(self, temp_cache_dir: Path) -> None:
        """Test roundtrip save/load."""
        cookies = [
            {"name": "session", "value": "abc123", "domain": ".spotify.com"},
        ]

        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            save_cookies(cookies)
            loaded = load_cookies()

            assert loaded is not None
            assert len(loaded) == 1
            assert loaded[0]["name"] == "session"
            assert loaded[0]["value"] == "abc123"

    def test_returns_none_when_file_missing(self, temp_cache_dir: Path) -> None:
        """Test that None is returned when cookie file doesn't exist."""
        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            # Don't save anything, just try to load
            loaded = load_cookies()

            assert loaded is None

    def test_returns_none_on_invalid_json(self, temp_cache_dir: Path) -> None:
        """Test that invalid JSON returns None."""
        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            path = get_cookie_path()
            path.write_text("not valid json {{{")

            loaded = load_cookies()

            assert loaded is None

    def test_returns_none_on_non_list_json(self, temp_cache_dir: Path) -> None:
        """Test that non-list JSON returns None."""
        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            path = get_cookie_path()
            path.write_text('{"key": "value"}')

            loaded = load_cookies()

            assert loaded is None


class TestClearCookies:
    """Tests for clear_cookies function."""

    def test_clears_existing_cookies(self, temp_cache_dir: Path) -> None:
        """Test that clear removes cookie file."""
        cookies = [{"name": "session", "value": "abc"}]

        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            save_cookies(cookies)
            path = get_cookie_path()
            assert path.exists()

            clear_cookies()

            assert not path.exists()

    def test_clear_nonexistent_is_noop(self, temp_cache_dir: Path) -> None:
        """Test that clearing non-existent file doesn't raise."""
        with patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir):
            # No cookies saved, should not raise
            clear_cookies()

            # Verify nothing was created
            path = temp_cache_dir / ".cache" / "kutx2spotify" / "spotify_cookies.json"
            assert not path.exists()


class TestHumanDelay:
    """Tests for human_delay async function."""

    def test_delays_in_expected_range(self) -> None:
        """Test that delay is within specified range."""
        with patch("kutx2spotify.browser.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None

            # Run with default values (1000-2000ms)
            asyncio.run(human_delay())

            # Should have been called once
            mock_sleep.assert_called_once()
            delay = mock_sleep.call_args[0][0]

            # Delay should be between 1.0 and 2.0 seconds
            assert 1.0 <= delay <= 2.0

    def test_custom_delay_range(self) -> None:
        """Test custom delay range."""
        with patch("kutx2spotify.browser.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None

            # Run with custom values (500-1000ms)
            asyncio.run(human_delay(min_ms=500, max_ms=1000))

            mock_sleep.assert_called_once()
            delay = mock_sleep.call_args[0][0]

            # Delay should be between 0.5 and 1.0 seconds
            assert 0.5 <= delay <= 1.0

    def test_delay_is_random(self) -> None:
        """Test that delay varies (is random)."""
        delays: list[float] = []

        with patch("kutx2spotify.browser.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None

            # Run multiple times to check for variation
            for _ in range(10):
                asyncio.run(human_delay(min_ms=1000, max_ms=2000))
                delays.append(mock_sleep.call_args[0][0])

        # With 10 samples, we should see some variation
        # (statistically very unlikely to get all same values)
        unique_delays = set(delays)
        assert len(unique_delays) > 1
