"""Tests for browser automation utilities."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kutx2spotify.browser import (
    SpotifyBrowser,
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

        # Mock locators
        mock_create_btn = MagicMock()
        mock_create_btn.click = AsyncMock()

        mock_title_element = MagicMock()
        mock_title_element.click = AsyncMock()

        mock_name_input = MagicMock()
        mock_name_input.fill = AsyncMock()

        mock_save_btn = MagicMock()
        mock_save_btn.click = AsyncMock()

        mock_first = MagicMock()
        mock_first.first = mock_title_element

        def locator_side_effect(selector: str) -> MagicMock:
            if "create-playlist-button" in selector:
                return mock_create_btn
            elif "playlist-name" in selector:
                return mock_first
            elif "name-input" in selector:
                return mock_name_input
            elif "save-button" in selector:
                return mock_save_btn
            return MagicMock()

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

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
                    mock_page.goto.assert_called_with(
                        "https://open.spotify.com/collection/playlists"
                    )
                    mock_create_btn.click.assert_called_once()
                    mock_title_element.click.assert_called_once()
                    mock_name_input.fill.assert_called_once_with("KUTX 2025-12-31")
                    mock_save_btn.click.assert_called_once()
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

                    mock_page.wait_for_url.assert_called_once_with("**/playlist/**")

        asyncio.run(test())
