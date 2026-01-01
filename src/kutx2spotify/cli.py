"""Click-based CLI for KUTX to Spotify integration."""

import asyncio
from datetime import datetime, time
from typing import Any

import click

from kutx2spotify.browser import SpotifyBrowser, select_best_match
from kutx2spotify.cache import KUTXCache, ResolutionCache
from kutx2spotify.kutx import KUTXClient
from kutx2spotify.matcher import Matcher
from kutx2spotify.models import MatchResult, Song
from kutx2spotify.output import (
    print_browser_header,
    print_browser_summary,
    print_browser_track_added,
    print_browser_track_skipped,
    print_error,
    print_info,
    print_issues,
    print_manual_links,
    print_match_list,
    print_playlist_created,
    print_playlist_header,
    print_summary,
)
from kutx2spotify.spotify import SpotifyClient


def parse_date(date_str: str) -> datetime:
    """Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string to parse.

    Returns:
        Parsed datetime.

    Raises:
        click.BadParameter: If the date format is invalid.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise click.BadParameter(
            f"Invalid date format: {date_str}. Expected YYYY-MM-DD."
        ) from e


def parse_time(time_str: str) -> time:
    """Parse a time string in HH:MM format.

    Args:
        time_str: Time string to parse.

    Returns:
        Parsed time.

    Raises:
        click.BadParameter: If the time format is invalid.
    """
    try:
        parsed = datetime.strptime(time_str, "%H:%M")
        return parsed.time()
    except ValueError as e:
        raise click.BadParameter(
            f"Invalid time format: {time_str}. Expected HH:MM."
        ) from e


def parse_resolve(resolve_str: str) -> tuple[int, int]:
    """Parse a resolve argument in INDEX=CHOICE format.

    Args:
        resolve_str: Resolve string like "3=1".

    Returns:
        Tuple of (track_index, choice_index).

    Raises:
        click.BadParameter: If the format is invalid.
    """
    try:
        parts = resolve_str.split("=")
        if len(parts) != 2:
            raise ValueError("Invalid format")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError) as e:
        raise click.BadParameter(
            f"Invalid resolve format: {resolve_str}. Expected INDEX=CHOICE (e.g., 3=1)."
        ) from e


class DateType(click.ParamType):
    """Click parameter type for dates."""

    name = "date"

    def convert(
        self,
        value: Any,
        param: click.Parameter | None,  # noqa: ARG002
        ctx: click.Context | None,  # noqa: ARG002
    ) -> datetime:
        """Convert string to datetime."""
        if isinstance(value, datetime):
            return value
        return parse_date(value)


class TimeType(click.ParamType):
    """Click parameter type for times."""

    name = "time"

    def convert(
        self,
        value: Any,
        param: click.Parameter | None,  # noqa: ARG002
        ctx: click.Context | None,  # noqa: ARG002
    ) -> time:
        """Convert string to time."""
        if isinstance(value, time):
            return value
        return parse_time(value)


DATE = DateType()
TIME = TimeType()


@click.command()
@click.option(
    "--date",
    "-d",
    type=DATE,
    required=True,
    help="Date to fetch playlist for (YYYY-MM-DD).",
)
@click.option(
    "--start",
    "-s",
    type=TIME,
    default=None,
    help="Start time filter (HH:MM).",
)
@click.option(
    "--end",
    "-e",
    type=TIME,
    default=None,
    help="End time filter (HH:MM).",
)
@click.option(
    "--name",
    "-n",
    default=None,
    help="Playlist name. Defaults to 'KUTX YYYY-MM-DD'.",
)
@click.option(
    "--preview",
    "-p",
    is_flag=True,
    help="Preview mode - show matches without creating playlist.",
)
@click.option(
    "--manual",
    "-m",
    is_flag=True,
    help="Manual mode - output Spotify search links.",
)
@click.option(
    "--cached",
    "-c",
    is_flag=True,
    help="Use cached KUTX data if available.",
)
@click.option(
    "--resolve",
    "-r",
    multiple=True,
    help="Apply saved resolution (INDEX=CHOICE, e.g., 3=1).",
)
@click.option(
    "--browser",
    "-b",
    is_flag=True,
    help="Use browser automation instead of Spotify API.",
)
@click.option(
    "--login",
    is_flag=True,
    help="Force fresh Spotify login (with --browser).",
)
@click.version_option(version="0.1.0", prog_name="kutx2spotify")
def main(
    date: datetime,
    start: time | None,
    end: time | None,
    name: str | None,
    preview: bool,
    manual: bool,
    cached: bool,
    resolve: tuple[str, ...],
    browser: bool,
    login: bool,
) -> None:
    """Fetch KUTX playlist and create Spotify playlist.

    Fetches the KUTX playlist for a given date and time range,
    matches songs to Spotify tracks, and creates a Spotify playlist.

    Example:
        kutx2spotify --date 2024-01-15 --start 14:00 --end 18:00 --preview
    """
    # Parse resolve options
    resolutions: list[tuple[int, int]] = []
    for r in resolve:
        resolutions.append(parse_resolve(r))

    # Setup clients and caches
    kutx_client = KUTXClient()
    kutx_cache = KUTXCache() if cached else None
    resolution_cache = ResolutionCache()
    spotify_client = SpotifyClient()

    # Fetch songs
    songs = _fetch_songs(
        kutx_client=kutx_client,
        kutx_cache=kutx_cache,
        date=date,
        start_time=start,
        end_time=end,
        use_cache=cached,
    )

    if not songs:
        print_error("No songs found for the specified date/time range.")
        raise SystemExit(1)

    print_info(f"Found {len(songs)} songs")

    # Browser mode: use Playwright instead of API
    if browser:
        playlist_name = name or f"KUTX {date.strftime('%Y-%m-%d')}"
        asyncio.run(_run_browser_workflow(songs, playlist_name, force_login=login))
        return

    # Match songs
    matcher = Matcher(
        spotify_client=spotify_client,
        resolution_cache=resolution_cache,
    )
    result = matcher.match_songs(songs)

    # Apply manual resolutions from CLI
    result = _apply_cli_resolutions(result, resolutions)

    # Format time strings for display
    start_str = start.strftime("%H:%M") if start else None
    end_str = end.strftime("%H:%M") if end else None
    date_str = date.strftime("%Y-%m-%d")

    # Print output
    print_playlist_header(date_str, start_str, end_str)
    print_match_list(result)
    print_issues(result)

    if manual:
        print_manual_links(result)
        print_summary(result, preview=True)
        return

    if preview:
        print_summary(result, preview=True)
        return

    # Create playlist
    _create_playlist(
        spotify_client=spotify_client,
        result=result,
        name=name,
        date=date,
    )


async def _run_browser_workflow(
    songs: list[Song], playlist_name: str, force_login: bool
) -> None:
    """Run browser-based workflow to create playlist.

    Args:
        songs: List of songs to add to playlist.
        playlist_name: Name for the new playlist.
        force_login: Force fresh login instead of using saved cookies.
    """
    async with SpotifyBrowser() as browser:
        # Login
        logged_in = await browser.ensure_logged_in(force_login=force_login)
        if not logged_in:
            print_error("Failed to log in to Spotify.")
            raise SystemExit(1)

        # Create playlist
        playlist_url = await browser.create_playlist(playlist_name)
        if not playlist_url:
            print_error("Failed to create playlist.")
            raise SystemExit(1)

        print_browser_header(playlist_name)

        added = 0
        skipped = 0

        for i, song in enumerate(songs, 1):
            query = f"{song.artist} {song.title}"
            results = await browser.search_tracks(query)
            selection = select_best_match(results, song.album, song.duration_ms)

            if selection.selected is None:
                print_browser_track_skipped(i, song, "no results")
                skipped += 1
                continue

            try:
                await browser.add_to_current_playlist(selection.selected, playlist_name)
                print_browser_track_added(i, song, selection)
                added += 1
            except Exception:
                print_browser_track_skipped(i, song, "failed to add")
                skipped += 1

        print_browser_summary(added, skipped, playlist_url)


def _fetch_songs(
    kutx_client: KUTXClient,
    kutx_cache: KUTXCache | None,
    date: datetime,
    start_time: time | None,
    end_time: time | None,
    use_cache: bool,
) -> list[Any]:
    """Fetch songs from KUTX, optionally using cache.

    Args:
        kutx_client: KUTX API client.
        kutx_cache: Optional cache for KUTX data.
        date: Date to fetch.
        start_time: Optional start time filter.
        end_time: Optional end time filter.
        use_cache: Whether to try cache first.

    Returns:
        List of songs.
    """
    songs = None

    # Try cache first if enabled
    if use_cache and kutx_cache:
        songs = kutx_cache.get(date)
        if songs:
            print_info("Using cached KUTX data")

    # Fetch from API if no cache hit
    if songs is None:
        print_info("Fetching from KUTX...")
        songs = kutx_client.fetch_range(date, start_time, end_time)

        # Cache the fetched data
        if kutx_cache:
            kutx_cache.set(date, songs)
    else:
        # Apply time filter to cached data
        if start_time or end_time:
            filtered = []
            for song in songs:
                song_time = song.played_at.time()
                if start_time and song_time < start_time:
                    continue
                if end_time and song_time > end_time:
                    continue
                filtered.append(song)
            songs = filtered

    return songs


def _apply_cli_resolutions(
    result: MatchResult, resolutions: list[tuple[int, int]]
) -> MatchResult:
    """Apply CLI-provided resolutions to match result.

    Note: This is a placeholder - full resolution would require
    additional Spotify API calls to get alternative tracks.
    For now, this just validates the resolution format.

    Args:
        result: Original match result.
        resolutions: List of (index, choice) tuples.

    Returns:
        Modified match result (currently unchanged).
    """
    for idx, choice in resolutions:
        if idx < 1 or idx > len(result.matches):
            print_error(f"Invalid resolution index: {idx}")
            continue
        # In a full implementation, we would look up alternative tracks
        # and apply the resolution. For now, we just acknowledge it.
        print_info(f"Resolution noted: track {idx} -> choice {choice}")

    return result


def _create_playlist(
    spotify_client: SpotifyClient,
    result: MatchResult,
    name: str | None,
    date: datetime,
) -> None:
    """Create a Spotify playlist from match results.

    Args:
        spotify_client: Spotify API client.
        result: Match result containing tracks.
        name: Optional playlist name.
        date: Date for default name.
    """
    if not spotify_client.is_configured:
        print_error(
            "Spotify API credentials not configured. "
            "Use --preview or --manual mode, or set SPOTIPY_* environment variables."
        )
        raise SystemExit(1)

    # Get track URIs
    track_uris = [m.track.uri for m in result.matches if m.track]

    if not track_uris:
        print_error("No tracks to add to playlist.")
        raise SystemExit(1)

    # Generate playlist name
    playlist_name = name or f"KUTX {date.strftime('%Y-%m-%d')}"

    # Create playlist and add tracks
    playlist_id = spotify_client.create_playlist(
        name=playlist_name,
        description=f"KUTX playlist from {date.strftime('%Y-%m-%d')}",
    )
    added_count = spotify_client.add_tracks(playlist_id, track_uris)
    playlist_url = spotify_client.get_playlist_url(playlist_id)

    print_playlist_created(playlist_url, playlist_name, added_count)
    print_summary(result, preview=False)


if __name__ == "__main__":
    main()
