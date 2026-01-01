"""Tests for browser automation utilities."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kutx2spotify.browser import (
    DURATION_TOLERANCE_MS,
    SearchResult,
    SelectionResult,
    SpotifyBrowser,
    albums_match,
    clear_cookies,
    get_cookie_path,
    human_delay,
    load_cookies,
    parse_duration,
    save_cookies,
    select_best_match,
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


@pytest.fixture
def mock_playwright() -> MagicMock:
    """Create mock playwright instance."""
    mock = MagicMock()
    mock.chromium.launch = AsyncMock()
    return mock


@pytest.fixture
def mock_browser() -> MagicMock:
    """Create mock browser instance."""
    mock = MagicMock()
    mock.close = AsyncMock()
    mock.new_context = AsyncMock()
    return mock


@pytest.fixture
def mock_context() -> MagicMock:
    """Create mock browser context."""
    mock = MagicMock()
    mock.close = AsyncMock()
    mock.new_page = AsyncMock()
    mock.add_cookies = AsyncMock()
    mock.cookies = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_page() -> MagicMock:
    """Create mock page instance."""
    mock = MagicMock()
    mock.goto = AsyncMock()
    mock.wait_for_selector = AsyncMock()
    mock.wait_for_url = AsyncMock()
    mock.url = "https://open.spotify.com/playlist/abc123"
    mock.locator = MagicMock()
    return mock


class TestSpotifyBrowserInit:
    """Tests for SpotifyBrowser initialization."""

    def test_default_headless_is_false(self) -> None:
        """Test that default headless mode is False."""
        browser = SpotifyBrowser()
        assert browser.headless is False

    def test_headless_can_be_set_true(self) -> None:
        """Test that headless mode can be enabled."""
        browser = SpotifyBrowser(headless=True)
        assert browser.headless is True

    def test_initial_state_is_none(self) -> None:
        """Test that all internal state is None before start."""
        browser = SpotifyBrowser()
        assert browser._playwright is None
        assert browser._browser is None
        assert browser._context is None
        assert browser._page is None


class TestSpotifyBrowserContextManager:
    """Tests for SpotifyBrowser async context manager."""

    def test_aenter_starts_browser(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that __aenter__ starts browser session."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser

        async def test() -> SpotifyBrowser:
            with patch("kutx2spotify.browser.async_playwright") as mock_pw:
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                browser = SpotifyBrowser()
                result = await browser.__aenter__()

                assert result is browser
                assert browser._playwright is not None
                assert browser._browser is not None
                assert browser._context is not None
                assert browser._page is not None
                return browser

        asyncio.run(test())

    def test_aexit_closes_browser(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that __aexit__ closes all resources."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        async def test() -> None:
            with patch("kutx2spotify.browser.async_playwright") as mock_pw:
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                browser = SpotifyBrowser()
                await browser.__aenter__()
                await browser.__aexit__(None, None, None)

                mock_context.close.assert_called_once()
                mock_browser.close.assert_called_once()
                mock_playwright.stop.assert_called_once()

        asyncio.run(test())

    def test_context_manager_usage(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test browser works as async context manager."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        async def test() -> None:
            with patch("kutx2spotify.browser.async_playwright") as mock_pw:
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    assert browser._page is not None

                # After exit, close should have been called
                mock_context.close.assert_called_once()

        asyncio.run(test())


class TestSpotifyBrowserPage:
    """Tests for SpotifyBrowser.page property."""

    def test_page_raises_when_not_started(self) -> None:
        """Test that page property raises when browser not started."""
        browser = SpotifyBrowser()
        with pytest.raises(RuntimeError, match="Browser not started"):
            _ = browser.page

    def test_page_returns_page_when_started(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that page property returns page after start."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        async def test() -> None:
            with patch("kutx2spotify.browser.async_playwright") as mock_pw:
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    page = browser.page
                    assert page is mock_page

        asyncio.run(test())


class TestSpotifyBrowserCookies:
    """Tests for SpotifyBrowser cookie handling."""

    def test_load_cookies_adds_to_context(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
        temp_cache_dir: Path,
    ) -> None:
        """Test that _load_cookies adds saved cookies to context."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        cookies = [{"name": "session", "value": "test123", "domain": ".spotify.com"}]

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                # Save cookies first
                save_cookies(cookies)

                async with SpotifyBrowser() as browser:
                    result = await browser._load_cookies()

                    assert result is True
                    mock_context.add_cookies.assert_called_once_with(cookies)

        asyncio.run(test())

    def test_load_cookies_returns_false_when_no_cookies(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
        temp_cache_dir: Path,
    ) -> None:
        """Test that _load_cookies returns False when no cookies saved."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    result = await browser._load_cookies()

                    assert result is False
                    mock_context.add_cookies.assert_not_called()

        asyncio.run(test())

    def test_save_cookies_writes_to_disk(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
        temp_cache_dir: Path,
    ) -> None:
        """Test that _save_cookies writes context cookies to disk."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        cookies = [{"name": "new_session", "value": "xyz", "domain": ".spotify.com"}]
        mock_context.cookies.return_value = cookies

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    await browser._save_cookies()

                    # Verify cookies were saved
                    loaded = load_cookies()
                    assert loaded is not None
                    assert loaded[0]["name"] == "new_session"

        asyncio.run(test())


class TestSpotifyBrowserLogin:
    """Tests for SpotifyBrowser login flow."""

    def test_is_logged_in_returns_true_when_user_widget_found(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that _is_logged_in returns True when user widget is found."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    result = await browser._is_logged_in()

                    assert result is True
                    mock_page.goto.assert_called_with("https://open.spotify.com")
                    mock_page.wait_for_selector.assert_called_once()

        asyncio.run(test())

    def test_is_logged_in_returns_false_on_timeout(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that _is_logged_in returns False when selector times out."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        # Simulate timeout
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    result = await browser._is_logged_in()

                    assert result is False

        asyncio.run(test())

    def test_wait_for_manual_login_success(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
        temp_cache_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that manual login returns True on success."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()
        mock_context.cookies.return_value = [{"name": "session", "value": "abc"}]

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    result = await browser._wait_for_manual_login()

                    assert result is True
                    mock_page.goto.assert_called_with("https://open.spotify.com/login")

        asyncio.run(test())
        captured = capsys.readouterr()
        assert "Please log in to Spotify" in captured.out
        assert "Login successful" in captured.out

    def test_wait_for_manual_login_timeout(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that manual login returns False on timeout."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))

        async def test() -> None:
            with patch("kutx2spotify.browser.async_playwright") as mock_pw:
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    result = await browser._wait_for_manual_login(timeout_seconds=1)

                    assert result is False

        asyncio.run(test())
        captured = capsys.readouterr()
        assert "Login timed out" in captured.out

    def test_ensure_logged_in_with_saved_cookies(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
        temp_cache_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that ensure_logged_in uses saved cookies when available."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        cookies = [{"name": "session", "value": "saved", "domain": ".spotify.com"}]

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir),
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                # Save cookies first
                save_cookies(cookies)

                async with SpotifyBrowser() as browser:
                    result = await browser.ensure_logged_in()

                    assert result is True
                    mock_context.add_cookies.assert_called_once()

        asyncio.run(test())
        captured = capsys.readouterr()
        assert "Logged in using saved session" in captured.out

    def test_ensure_logged_in_force_login(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
        temp_cache_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that force_login skips cookie restoration."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()
        mock_context.cookies.return_value = []

        cookies = [{"name": "session", "value": "saved", "domain": ".spotify.com"}]

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.Path.home", return_value=temp_cache_dir),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                # Save cookies (should be ignored with force_login)
                save_cookies(cookies)

                async with SpotifyBrowser() as browser:
                    result = await browser.ensure_logged_in(force_login=True)

                    assert result is True
                    # add_cookies should not be called due to force_login
                    mock_context.add_cookies.assert_not_called()

        asyncio.run(test())
        captured = capsys.readouterr()
        assert "Please log in to Spotify" in captured.out


class TestSpotifyBrowserCreatePlaylist:
    """Tests for SpotifyBrowser.create_playlist."""

    def test_create_playlist_returns_url(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that create_playlist returns the playlist URL."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        # Mock locators - all return a mock that works for any method
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_locator.first = mock_locator
        mock_page.locator = MagicMock(return_value=mock_locator)

        async def test() -> str | None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    url = await browser.create_playlist("KUTX 2025-12-31")

                    assert url == "https://open.spotify.com/playlist/abc123"
                    # Verify goto was called (first to main page)
                    assert mock_page.goto.called
                    return url

        result = asyncio.run(test())
        assert result is not None

    def test_create_playlist_waits_for_url_change(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that create_playlist waits for URL to change to playlist."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        # Mock all locators
        mock_btn = MagicMock()
        mock_btn.click = AsyncMock()
        mock_btn.fill = AsyncMock()
        mock_btn.first = mock_btn
        mock_page.locator = MagicMock(return_value=mock_btn)

        async def test() -> None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    await browser.create_playlist("Test Playlist")

                    # Verify wait_for_url was called with the playlist pattern
                    mock_page.wait_for_url.assert_called_with(
                        "**/playlist/**", timeout=10000
                    )

        asyncio.run(test())

    def test_create_playlist_returns_none_on_url_wait_failure(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that create_playlist returns None when URL wait times out."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        # Mock locators that work (playlist creation succeeds)
        mock_btn = MagicMock()
        mock_btn.click = AsyncMock()
        mock_btn.fill = AsyncMock()
        mock_btn.first = mock_btn
        mock_page.locator = MagicMock(return_value=mock_btn)

        # But wait_for_url fails (playlist page never loads)
        mock_page.wait_for_url = AsyncMock(side_effect=Exception("Timeout"))

        async def test() -> str | None:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    return await browser.create_playlist("Test")

        result = asyncio.run(test())
        assert result is None


class TestAlbumsMatch:
    """Tests for albums_match function."""

    def test_exact_match(self) -> None:
        """Test that identical albums match."""
        assert albums_match("Head Hunters", "Head Hunters") is True

    def test_case_insensitive_match(self) -> None:
        """Test that albums match regardless of case."""
        assert albums_match("Head Hunters", "head hunters") is True
        assert albums_match("HEAD HUNTERS", "Head Hunters") is True

    def test_no_match(self) -> None:
        """Test that different albums don't match."""
        assert albums_match("Head Hunters", "Thrust") is False

    def test_empty_strings_match(self) -> None:
        """Test that empty strings match each other."""
        assert albums_match("", "") is True


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_parse_simple_duration(self) -> None:
        """Test parsing simple M:SS format."""
        assert parse_duration("3:45") == 225000  # 3*60 + 45 = 225 seconds

    def test_parse_long_duration(self) -> None:
        """Test parsing longer durations."""
        assert parse_duration("10:30") == 630000  # 10*60 + 30 = 630 seconds

    def test_parse_short_duration(self) -> None:
        """Test parsing short durations."""
        assert parse_duration("0:30") == 30000  # 30 seconds

    def test_parse_with_whitespace(self) -> None:
        """Test parsing duration with whitespace."""
        assert parse_duration("  3:45  ") == 225000

    def test_parse_invalid_format(self) -> None:
        """Test parsing invalid format returns 0."""
        assert parse_duration("invalid") == 0
        assert parse_duration("3:4") == 0  # Not two digit seconds
        assert parse_duration("") == 0


class TestSearchResultDurationDisplay:
    """Tests for SearchResult.duration_display property."""

    def test_duration_display_simple(self) -> None:
        """Test basic duration display formatting."""
        mock_locator = MagicMock()
        result = SearchResult(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=225000,  # 3:45
            row_locator=mock_locator,
        )
        assert result.duration_display == "3:45"

    def test_duration_display_zero_padded(self) -> None:
        """Test seconds are zero-padded."""
        mock_locator = MagicMock()
        result = SearchResult(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=305000,  # 5:05
            row_locator=mock_locator,
        )
        assert result.duration_display == "5:05"

    def test_duration_display_short(self) -> None:
        """Test short duration formatting."""
        mock_locator = MagicMock()
        result = SearchResult(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=30000,  # 0:30
            row_locator=mock_locator,
        )
        assert result.duration_display == "0:30"


class TestSelectBestMatch:
    """Tests for select_best_match function."""

    @pytest.fixture
    def mock_results(self) -> list[SearchResult]:
        """Create mock search results for testing."""
        mock_locator = MagicMock()
        return [
            SearchResult(
                title="Song 1",
                artist="Artist 1",
                album="Target Album",
                duration_ms=180000,  # 3:00
                row_locator=mock_locator,
            ),
            SearchResult(
                title="Song 2",
                artist="Artist 2",
                album="Different Album",
                duration_ms=180000,  # 3:00
                row_locator=mock_locator,
            ),
            SearchResult(
                title="Song 3",
                artist="Artist 3",
                album="Another Album",
                duration_ms=200000,  # 3:20
                row_locator=mock_locator,
            ),
        ]

    def test_exact_match_album_and_duration(
        self, mock_results: list[SearchResult]
    ) -> None:
        """Test exact match is found when album and duration match."""
        result = select_best_match(
            mock_results,
            target_album="Target Album",
            target_duration_ms=180000,
        )
        assert result.selected is not None
        assert result.selected.album == "Target Album"
        assert result.reason == "exact_match"
        assert len(result.alternatives) == 2

    def test_album_match_only(self) -> None:
        """Test album match when duration differs."""
        mock_locator = MagicMock()
        results = [
            SearchResult(
                title="Song",
                artist="Artist",
                album="Target Album",
                duration_ms=180000,  # 3:00
                row_locator=mock_locator,
            ),
        ]
        # Target duration is very different
        result = select_best_match(
            results,
            target_album="Target Album",
            target_duration_ms=300000,  # 5:00 - way off
        )
        assert result.selected is not None
        assert result.reason == "album_match"

    def test_duration_match_only(self) -> None:
        """Test duration match when album differs."""
        mock_locator = MagicMock()
        results = [
            SearchResult(
                title="Song",
                artist="Artist",
                album="Different Album",
                duration_ms=180000,  # 3:00
                row_locator=mock_locator,
            ),
        ]
        result = select_best_match(
            results,
            target_album="Target Album",
            target_duration_ms=185000,  # Within tolerance
        )
        assert result.selected is not None
        assert result.reason == "duration_match"

    def test_first_result_fallback(self) -> None:
        """Test first result is used when no matches."""
        mock_locator = MagicMock()
        results = [
            SearchResult(
                title="Song 1",
                artist="Artist",
                album="Different Album",
                duration_ms=180000,
                row_locator=mock_locator,
            ),
            SearchResult(
                title="Song 2",
                artist="Artist",
                album="Another Album",
                duration_ms=200000,
                row_locator=mock_locator,
            ),
        ]
        result = select_best_match(
            results,
            target_album="Target Album",
            target_duration_ms=300000,  # No match
        )
        assert result.selected is not None
        assert result.selected.title == "Song 1"
        assert result.reason == "first_result"
        assert len(result.alternatives) == 1

    def test_no_results(self) -> None:
        """Test no results case."""
        result = select_best_match(
            [],
            target_album="Target Album",
            target_duration_ms=180000,
        )
        assert result.selected is None
        assert result.reason == "no_results"
        assert result.alternatives == []

    def test_duration_tolerance_boundary(self) -> None:
        """Test duration matching at tolerance boundary."""
        mock_locator = MagicMock()
        results = [
            SearchResult(
                title="Song",
                artist="Artist",
                album="Different Album",
                duration_ms=180000,
                row_locator=mock_locator,
            ),
        ]
        # At exactly the tolerance boundary
        result = select_best_match(
            results,
            target_album="Wrong Album",
            target_duration_ms=180000 + DURATION_TOLERANCE_MS,
        )
        assert result.reason == "duration_match"

        # Just outside tolerance
        result = select_best_match(
            results,
            target_album="Wrong Album",
            target_duration_ms=180000 + DURATION_TOLERANCE_MS + 1,
        )
        assert result.reason == "first_result"


class TestSpotifyBrowserSearchTracks:
    """Tests for SpotifyBrowser.search_tracks method."""

    def test_search_tracks_returns_results(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that search_tracks returns parsed results."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        # Mock row elements
        mock_row = MagicMock()
        mock_title = MagicMock()
        mock_title.inner_text = AsyncMock(return_value="Test Song")
        mock_title.first = mock_title

        mock_artist_links = MagicMock()
        mock_artist_links.count = AsyncMock(return_value=1)
        mock_artist_links.nth = MagicMock(
            return_value=MagicMock(
                inner_text=AsyncMock(return_value="Test Artist"),
                get_attribute=AsyncMock(return_value="/artist/123"),
            )
        )

        mock_album_links = MagicMock()
        mock_album_links.count = AsyncMock(return_value=1)
        mock_album_links.first = MagicMock(
            inner_text=AsyncMock(return_value="Test Album")
        )

        mock_duration = MagicMock()
        mock_duration.inner_text = AsyncMock(return_value="3:45")
        mock_duration.first = mock_duration

        def row_locator_side_effect(selector: str) -> MagicMock:
            if "internal-track-link" in selector:
                return mock_title
            elif "tracklist-row-subtitle" in selector and "album" in selector:
                return mock_album_links
            elif "tracklist-row-subtitle" in selector:
                return mock_artist_links
            elif "duration" in selector:
                return mock_duration
            return MagicMock()

        mock_row.locator = MagicMock(side_effect=row_locator_side_effect)

        mock_rows = MagicMock()
        mock_rows.count = AsyncMock(return_value=1)
        mock_rows.nth = MagicMock(return_value=mock_row)

        def page_locator_side_effect(selector: str) -> MagicMock:
            if "tracklist-row" in selector:
                return mock_rows
            return MagicMock()

        mock_page.locator = MagicMock(side_effect=page_locator_side_effect)

        async def run_test() -> list[SearchResult]:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    results = await browser.search_tracks("Test Artist Test Song")
                    return results

        results = asyncio.run(run_test())
        assert len(results) == 1
        assert results[0].title == "Test Song"
        assert results[0].artist == "Test Artist"
        assert results[0].album == "Test Album"
        assert results[0].duration_ms == 225000

    def test_search_tracks_no_results(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that search_tracks returns empty list when no results."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        # Simulate timeout (no results)
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))

        async def run_test() -> list[SearchResult]:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    results = await browser.search_tracks("nonexistent track")
                    return results

        results = asyncio.run(run_test())
        assert results == []

    def test_search_tracks_limit(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that search_tracks respects limit parameter."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        # Mock row elements
        mock_row = MagicMock()
        mock_title = MagicMock()
        mock_title.inner_text = AsyncMock(return_value="Test Song")
        mock_title.first = mock_title

        mock_artist_links = MagicMock()
        mock_artist_links.count = AsyncMock(return_value=0)

        mock_album_links = MagicMock()
        mock_album_links.count = AsyncMock(return_value=0)

        mock_duration = MagicMock()
        mock_duration.inner_text = AsyncMock(return_value="3:00")
        mock_duration.first = mock_duration

        def row_locator_side_effect(selector: str) -> MagicMock:
            if "internal-track-link" in selector:
                return mock_title
            elif "tracklist-row-subtitle" in selector and "album" in selector:
                return mock_album_links
            elif "tracklist-row-subtitle" in selector:
                return mock_artist_links
            elif "duration" in selector:
                return mock_duration
            return MagicMock()

        mock_row.locator = MagicMock(side_effect=row_locator_side_effect)

        mock_rows = MagicMock()
        mock_rows.count = AsyncMock(return_value=10)  # 10 available
        mock_rows.nth = MagicMock(return_value=mock_row)

        mock_page.locator = MagicMock(return_value=mock_rows)

        async def run_test() -> list[SearchResult]:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    results = await browser.search_tracks("query", limit=3)
                    return results

        results = asyncio.run(run_test())
        assert len(results) == 3  # Limited to 3


class TestSpotifyBrowserAddToPlaylist:
    """Tests for SpotifyBrowser.add_to_current_playlist method."""

    def test_add_to_playlist_success(
        self,
        mock_playwright: MagicMock,
        mock_browser: MagicMock,
        mock_context: MagicMock,
        mock_page: MagicMock,
    ) -> None:
        """Test that add_to_current_playlist adds track successfully."""
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_playwright.stop = AsyncMock()

        # Mock the row locator for right-click
        mock_row_locator = MagicMock()
        mock_row_locator.click = AsyncMock()

        # Mock add to playlist button
        mock_add_btn = MagicMock()
        mock_add_btn.click = AsyncMock()

        # Mock playlist option
        mock_playlist_opt = MagicMock()
        mock_playlist_opt.click = AsyncMock()

        def page_locator_side_effect(selector: str) -> MagicMock:
            if "add-to-playlist-button" in selector:
                return mock_add_btn
            elif "has-text" in selector:
                return mock_playlist_opt
            return MagicMock()

        mock_page.locator = MagicMock(side_effect=page_locator_side_effect)

        search_result = SearchResult(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_ms=180000,
            row_locator=mock_row_locator,
        )

        async def run_test() -> bool:
            with (
                patch("kutx2spotify.browser.async_playwright") as mock_pw,
                patch("kutx2spotify.browser.human_delay", new=AsyncMock()),
            ):
                mock_pw_instance = MagicMock()
                mock_pw_instance.start = AsyncMock(return_value=mock_playwright)
                mock_pw.return_value = mock_pw_instance

                async with SpotifyBrowser() as browser:
                    result = await browser.add_to_current_playlist(
                        search_result, "My Playlist"
                    )
                    return result

        result = asyncio.run(run_test())
        assert result is True
        mock_row_locator.click.assert_called_once_with(button="right")
        mock_add_btn.click.assert_called_once()
        mock_playlist_opt.click.assert_called_once()


class TestSelectionResultDataclass:
    """Tests for SelectionResult dataclass."""

    def test_selection_result_with_selected(self) -> None:
        """Test SelectionResult with a selected track."""
        mock_locator = MagicMock()
        selected = SearchResult(
            title="Song",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            row_locator=mock_locator,
        )
        result = SelectionResult(
            selected=selected,
            reason="exact_match",
            alternatives=[],
        )
        assert result.selected is not None
        assert result.reason == "exact_match"
        assert result.alternatives == []

    def test_selection_result_no_selected(self) -> None:
        """Test SelectionResult with no selected track."""
        result = SelectionResult(
            selected=None,
            reason="no_results",
            alternatives=[],
        )
        assert result.selected is None
        assert result.reason == "no_results"


class TestDurationToleranceConstant:
    """Tests for DURATION_TOLERANCE_MS constant."""

    def test_tolerance_is_10_seconds(self) -> None:
        """Test that duration tolerance is 10 seconds."""
        assert DURATION_TOLERANCE_MS == 10000
