"""Rich-based output formatting for CLI."""

from urllib.parse import quote_plus

from rich.console import Console
from rich.text import Text

from kutx2spotify.models import Match, MatchResult, MatchStatus

console = Console()


def format_duration(duration_ms: int) -> str:
    """Format duration in milliseconds as MM:SS.

    Args:
        duration_ms: Duration in milliseconds.

    Returns:
        Formatted string like "4:12".
    """
    total_seconds = duration_ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def format_duration_diff(diff_ms: int) -> str:
    """Format duration difference with sign.

    Args:
        diff_ms: Duration difference in milliseconds (positive = longer).

    Returns:
        Formatted string like "+15s" or "-5s".
    """
    diff_seconds = diff_ms // 1000
    sign = "+" if diff_seconds >= 0 else ""
    return f"{sign}{diff_seconds}s"


def generate_spotify_search_url(title: str, artist: str) -> str:
    """Generate a Spotify search URL for manual searching.

    Args:
        title: Track title.
        artist: Artist name.

    Returns:
        Spotify search URL.
    """
    query = f"{title} {artist}"
    encoded_query = quote_plus(query)
    return f"https://open.spotify.com/search/{encoded_query}"


def print_playlist_header(
    date_str: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> None:
    """Print the playlist header.

    Args:
        date_str: Date string (e.g., "2024-01-15").
        start_time: Start time string (e.g., "14:00"). Optional.
        end_time: End time string (e.g., "18:00"). Optional.
    """
    if start_time and end_time:
        header = f"KUTX Playlist: {date_str} {start_time} - {end_time}"
    elif start_time:
        header = f"KUTX Playlist: {date_str} {start_time} - end of day"
    elif end_time:
        header = f"KUTX Playlist: {date_str} start of day - {end_time}"
    else:
        header = f"KUTX Playlist: {date_str}"

    console.print()
    console.print(header, style="bold")
    console.print("=" * len(header))
    console.print()


def print_match_list(result: MatchResult) -> None:
    """Print the list of matches with asterisks for issues.

    Args:
        result: MatchResult containing all matches.
    """
    for idx, match in enumerate(result.matches, 1):
        _print_match_line(idx, match)


def _print_match_line(idx: int, match: Match) -> None:
    """Print a single match line.

    Args:
        idx: 1-based index.
        match: The match to print.
    """
    song = match.song
    prefix = "*" if match.has_issue else " "
    duration = format_duration(song.duration_ms)

    # Build the line: "* 3. Title - Artist (Album) [4:12]"
    line = Text()
    line.append(f"{prefix} ")

    if match.has_issue:
        line.append(f"{idx:2d}. ", style="yellow bold")
    else:
        line.append(f"{idx:2d}. ")

    line.append(f"{song.title}", style="bold" if not match.has_issue else "yellow bold")
    line.append(f" - {song.artist}")

    if song.album:
        line.append(f" ({song.album})", style="dim")

    line.append(f" [{duration}]", style="dim")

    console.print(line)


def print_issues(result: MatchResult) -> None:
    """Print detailed information about matches with issues.

    Args:
        result: MatchResult containing all matches.
    """
    issues = result.issues
    if not issues:
        return

    console.print()
    console.print("-" * 41)
    console.print(f"Exact matches: {result.exact_matches}/{result.total}")
    console.print()
    console.print("ISSUES:", style="bold yellow")

    for idx, match in enumerate(result.matches, 1):
        if not match.has_issue:
            continue
        _print_issue_detail(idx, match)


def _print_issue_detail(idx: int, match: Match) -> None:
    """Print detailed information about a single issue.

    Args:
        idx: 1-based index of the match.
        match: The match with an issue.
    """
    song = match.song
    track = match.track

    console.print(f"* #{idx}: {song.title} - {song.artist}", style="yellow")

    if match.status == MatchStatus.NOT_FOUND:
        console.print("  Not found on Spotify", style="red")
        console.print(
            f"  Search: {generate_spotify_search_url(song.title, song.artist)}"
        )
    elif match.status == MatchStatus.DURATION_MISMATCH and track:
        console.print(f"  KUTX album: {song.album}")
        diff_ms = track.duration_ms - song.duration_ms
        track_duration = format_duration(track.duration_ms)
        diff_str = format_duration_diff(diff_ms)
        console.print(f"  Recommended: {track.album} ({track_duration}, {diff_str})")
        console.print(f"  Resolve: --resolve {idx}=1")


def print_manual_links(result: MatchResult) -> None:
    """Print Spotify search links for manual mode.

    Args:
        result: MatchResult containing all matches.
    """
    console.print()
    console.print("Manual Search Links:", style="bold")
    console.print("-" * 41)

    for idx, match in enumerate(result.matches, 1):
        song = match.song
        url = generate_spotify_search_url(song.title, song.artist)
        console.print(f"{idx:2d}. {song.title} - {song.artist}")
        console.print(f"    {url}", style="dim")


def print_summary(result: MatchResult, preview: bool = False) -> None:
    """Print summary statistics.

    Args:
        result: MatchResult containing all matches.
        preview: Whether this is a preview run (no Spotify changes).
    """
    console.print()
    console.print("-" * 41)

    if preview:
        console.print("[Preview mode - no changes made]", style="dim")
        console.print()

    console.print(f"Total tracks: {result.total}")
    console.print(f"Matched: {result.found}")
    console.print(f"Not found: {result.not_found}")
    console.print(f"Exact matches: {result.exact_matches}")

    issues_count = len(result.issues)
    if issues_count > 0:
        console.print(f"Issues: {issues_count}", style="yellow")
    else:
        console.print("Issues: 0", style="green")


def print_playlist_created(url: str, name: str, track_count: int) -> None:
    """Print playlist creation success message.

    Args:
        url: Spotify playlist URL.
        name: Playlist name.
        track_count: Number of tracks added.
    """
    console.print()
    console.print("Playlist created!", style="bold green")
    console.print(f"Name: {name}")
    console.print(f"Tracks: {track_count}")
    console.print(f"URL: {url}")


def print_error(message: str) -> None:
    """Print an error message.

    Args:
        message: Error message to print.
    """
    console.print(f"Error: {message}", style="bold red")


def print_warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: Warning message to print.
    """
    console.print(f"Warning: {message}", style="yellow")


def print_info(message: str) -> None:
    """Print an informational message.

    Args:
        message: Info message to print.
    """
    console.print(message, style="dim")
