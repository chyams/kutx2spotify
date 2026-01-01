"""Browser automation utilities for Spotify integration."""

from __future__ import annotations

import asyncio
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from playwright.async_api import async_playwright

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Locator, Page

# Duration tolerance in milliseconds (10 seconds)
DURATION_TOLERANCE_MS = 10_000


def albums_match(album1: str, album2: str) -> bool:
    """Check if albums match (case-insensitive).

    Args:
        album1: First album name.
        album2: Second album name.

    Returns:
        True if albums match.
    """
    return album1.lower() == album2.lower()


@dataclass
class SearchResult:
    """A search result from Spotify web."""

    title: str
    artist: str
    album: str
    duration_ms: int
    row_locator: Locator

    @property
    def duration_display(self) -> str:
        """Format duration as M:SS string."""
        seconds = self.duration_ms // 1000
        return f"{seconds // 60}:{seconds % 60:02d}"


@dataclass
class SelectionResult:
    """Result of selecting a track."""

    selected: SearchResult | None
    reason: str  # exact_match, album_match, duration_match, first_result, no_results
    alternatives: list[SearchResult]


def parse_duration(duration_str: str) -> int:
    """Parse duration string (M:SS) to milliseconds.

    Args:
        duration_str: Duration in M:SS format (e.g., "3:45").

    Returns:
        Duration in milliseconds.
    """
    match = re.match(r"(\d+):(\d{2})", duration_str.strip())
    if not match:
        return 0
    minutes, seconds = int(match.group(1)), int(match.group(2))
    return (minutes * 60 + seconds) * 1000


def select_best_match(
    results: list[SearchResult],
    target_album: str,
    target_duration_ms: int,
) -> SelectionResult:
    """Select best matching track from search results.

    Priority:
    1. Album match + duration match -> exact_match
    2. Album match only -> album_match
    3. Duration match only -> duration_match
    4. First result -> first_result
    5. No results -> no_results

    Args:
        results: List of search results.
        target_album: Album name to match.
        target_duration_ms: Duration in milliseconds to match.

    Returns:
        SelectionResult with selected track and reason.
    """
    if not results:
        return SelectionResult(selected=None, reason="no_results", alternatives=[])

    def duration_matches(result: SearchResult) -> bool:
        return abs(result.duration_ms - target_duration_ms) <= DURATION_TOLERANCE_MS

    # Priority 1: Album match + duration match
    for result in results:
        if albums_match(result.album, target_album) and duration_matches(result):
            alternatives = [r for r in results if r is not result]
            return SelectionResult(
                selected=result, reason="exact_match", alternatives=alternatives
            )

    # Priority 2: Album match only
    for result in results:
        if albums_match(result.album, target_album):
            alternatives = [r for r in results if r is not result]
            return SelectionResult(
                selected=result, reason="album_match", alternatives=alternatives
            )

    # Priority 3: Duration match only
    for result in results:
        if duration_matches(result):
            alternatives = [r for r in results if r is not result]
            return SelectionResult(
                selected=result, reason="duration_match", alternatives=alternatives
            )

    # Priority 4: First result
    alternatives = results[1:] if len(results) > 1 else []
    return SelectionResult(
        selected=results[0], reason="first_result", alternatives=alternatives
    )


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

    async def search_tracks(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Search for tracks on Spotify web.

        Args:
            query: Search query string (e.g., "artist title").
            limit: Maximum number of results to return.

        Returns:
            List of SearchResult objects with parsed track information.
        """
        await human_delay()
        # URL encode the query for search
        encoded_query = query.replace(" ", "%20")
        search_url = f"{self.SPOTIFY_URL}/search/{encoded_query}/tracks"
        await self.page.goto(search_url)
        await human_delay()

        try:
            await self.page.wait_for_selector(
                '[data-testid="tracklist-row"]', timeout=10000
            )
        except Exception:
            # No results found
            return []

        rows = self.page.locator('[data-testid="tracklist-row"]')
        count = min(await rows.count(), limit)

        results: list[SearchResult] = []
        for i in range(count):
            row = rows.nth(i)

            # Parse title from the track-title link
            title_elem = row.locator('[data-testid="internal-track-link"]').first
            title = await title_elem.inner_text()

            # Parse artist(s) - multiple links in the span
            artist_links = row.locator('span[data-testid="tracklist-row-subtitle"] a')
            artist_count = await artist_links.count()
            artists: list[str] = []
            for j in range(artist_count):
                artist_text = await artist_links.nth(j).inner_text()
                # Skip album links (those containing album in href)
                href = await artist_links.nth(j).get_attribute("href") or ""
                if "/artist/" in href:
                    artists.append(artist_text)
            artist = ", ".join(artists) if artists else ""

            # Parse album - typically the last link in subtitle
            album_links = row.locator(
                'span[data-testid="tracklist-row-subtitle"] a[href*="/album/"]'
            )
            album = ""
            if await album_links.count() > 0:
                album = await album_links.first.inner_text()

            # Parse duration from the duration column
            duration_elem = row.locator('[data-testid="tracklist-row-duration"]').first
            duration_text = await duration_elem.inner_text()
            duration_ms = parse_duration(duration_text)

            results.append(
                SearchResult(
                    title=title,
                    artist=artist,
                    album=album,
                    duration_ms=duration_ms,
                    row_locator=row,
                )
            )

        return results

    async def add_to_current_playlist(
        self, result: SearchResult, playlist_name: str
    ) -> bool:
        """Add a track to the current playlist via context menu.

        Args:
            result: SearchResult containing the row_locator to click.
            playlist_name: Name of the playlist to add to.

        Returns:
            True if track was added successfully.
        """
        await human_delay()

        # Right-click on the row to open context menu
        await result.row_locator.click(button="right")
        await human_delay(500, 1000)

        # Click "Add to playlist" menu item
        add_to_playlist = self.page.locator(
            'button[data-testid="add-to-playlist-button"]'
        )
        await add_to_playlist.click()
        await human_delay(500, 1000)

        # Select the target playlist from the submenu
        playlist_option = self.page.locator(f'button:has-text("{playlist_name}")')
        await playlist_option.click()
        await human_delay()

        return True
