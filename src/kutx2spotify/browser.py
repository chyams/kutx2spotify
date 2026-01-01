"""Browser automation utilities for Spotify integration."""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from playwright.async_api import async_playwright

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page


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


class SpotifyBrowser:
    """Playwright-based Spotify web automation."""

    SPOTIFY_URL = "https://open.spotify.com"

    def __init__(self, headless: bool = False) -> None:
        """Initialize SpotifyBrowser.

        Args:
            headless: Run browser in headless mode. Defaults to False for
                manual login flow.
        """
        self.headless = headless
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> SpotifyBrowser:
        """Start browser session."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Close browser session."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def page(self) -> Page:
        """Get current page, raising if browser not started."""
        if not self._page:
            raise RuntimeError("Browser not started. Use 'async with SpotifyBrowser()'")
        return self._page

    async def _load_cookies(self) -> bool:
        """Load cookies from disk into browser context.

        Returns:
            True if cookies were loaded, False otherwise.
        """
        cookies = load_cookies()
        if cookies and self._context:
            await self._context.add_cookies(cookies)  # type: ignore[arg-type]
            return True
        return False

    async def _save_cookies(self) -> None:
        """Save cookies from browser context to disk."""
        if self._context:
            cookies = await self._context.cookies()
            save_cookies(cookies)  # type: ignore[arg-type]

    async def _is_logged_in(self) -> bool:
        """Check if user is logged in to Spotify.

        Returns:
            True if logged in, False otherwise.
        """
        await self.page.goto(self.SPOTIFY_URL)
        await human_delay()
        try:
            await self.page.wait_for_selector(
                '[data-testid="user-widget-link"]', timeout=5000
            )
            return True
        except Exception:
            return False

    async def _wait_for_manual_login(self, timeout_seconds: int = 120) -> bool:
        """Wait for user to manually log in.

        Args:
            timeout_seconds: Maximum time to wait for login.

        Returns:
            True if login successful, False if timed out.
        """
        print("Please log in to Spotify in the browser window...")
        await self.page.goto(f"{self.SPOTIFY_URL}/login")
        try:
            await self.page.wait_for_selector(
                '[data-testid="user-widget-link"]', timeout=timeout_seconds * 1000
            )
            await self._save_cookies()
            print("Login successful! Cookies saved.")
            return True
        except Exception:
            print("Login timed out.")
            return False

    async def ensure_logged_in(self, force_login: bool = False) -> bool:
        """Ensure user is logged in, prompting for manual login if needed.

        Args:
            force_login: Skip cookie restoration and force manual login.

        Returns:
            True if logged in, False if login failed/timed out.
        """
        if not force_login:
            await self._load_cookies()
            if await self._is_logged_in():
                print("Logged in using saved session.")
                return True
        return await self._wait_for_manual_login()

    async def create_playlist(self, name: str) -> str | None:
        """Create a new playlist with the given name.

        Args:
            name: Name for the new playlist.

        Returns:
            URL of the created playlist, or None if creation failed.
        """
        await human_delay()
        await self.page.goto(f"{self.SPOTIFY_URL}/collection/playlists")
        await human_delay()

        create_btn = self.page.locator('[data-testid="create-playlist-button"]')
        await create_btn.click()
        await human_delay()

        await self.page.wait_for_url("**/playlist/**")
        playlist_url: str = self.page.url

        # Rename playlist
        title_element = self.page.locator('[data-testid="playlist-name"]').first
        await title_element.click()
        await human_delay()

        name_input = self.page.locator(
            'input[data-testid="playlist-edit-details-name-input"]'
        )
        await name_input.fill(name)
        await human_delay()

        save_btn = self.page.locator(
            'button[data-testid="playlist-edit-details-save-button"]'
        )
        await save_btn.click()
        await human_delay()

        return playlist_url
