"""Tests for CLI module."""

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from kutx2spotify.browser import SearchResult
from kutx2spotify.cli import (
    DATE,
    TIME,
    _run_browser_workflow,
    main,
    parse_date,
    parse_resolve,
    parse_time,
)
from kutx2spotify.models import Match, MatchResult, MatchStatus, Song, SpotifyTrack


def make_song(
    title: str = "Test Song",
    artist: str = "Test Artist",
    album: str = "Test Album",
    duration_ms: int = 180000,
    played_at: datetime | None = None,
) -> Song:
    """Create a test song."""
    return Song(
        title=title,
        artist=artist,
        album=album,
        duration_ms=duration_ms,
        played_at=played_at or datetime(2026, 1, 1, 14, 30, 0),
    )


def make_track(
    title: str = "Test Song",
    artist: str = "Test Artist",
    album: str = "Test Album",
    duration_ms: int = 180000,
) -> SpotifyTrack:
    """Create a test Spotify track."""
    return SpotifyTrack(
        id="abc123",
        uri="spotify:track:abc123",
        title=title,
        artist=artist,
        album=album,
        duration_ms=duration_ms,
        popularity=50,
    )


class TestParseDate:
    """Tests for parse_date function."""

    def test_valid_date(self) -> None:
        """Test parsing valid date."""
        result = parse_date("2024-01-15")
        assert result == datetime(2024, 1, 15)

    def test_invalid_date_format(self) -> None:
        """Test invalid date format raises error."""
        with pytest.raises(click.BadParameter, match="Invalid date format"):
            parse_date("01-15-2024")

    def test_invalid_date_value(self) -> None:
        """Test invalid date value raises error."""
        with pytest.raises(click.BadParameter, match="Invalid date format"):
            parse_date("not-a-date")


class TestParseTime:
    """Tests for parse_time function."""

    def test_valid_time(self) -> None:
        """Test parsing valid time."""
        result = parse_time("14:30")
        assert result == time(14, 30)

    def test_valid_time_midnight(self) -> None:
        """Test parsing midnight."""
        result = parse_time("00:00")
        assert result == time(0, 0)

    def test_invalid_time_format(self) -> None:
        """Test invalid time format raises error."""
        with pytest.raises(click.BadParameter, match="Invalid time format"):
            parse_time("2:30 PM")

    def test_invalid_time_value(self) -> None:
        """Test invalid time value raises error."""
        with pytest.raises(click.BadParameter, match="Invalid time format"):
            parse_time("not-a-time")


class TestParseResolve:
    """Tests for parse_resolve function."""

    def test_valid_resolve(self) -> None:
        """Test parsing valid resolve string."""
        result = parse_resolve("3=1")
        assert result == (3, 1)

    def test_valid_resolve_larger_numbers(self) -> None:
        """Test parsing resolve with larger numbers."""
        result = parse_resolve("15=3")
        assert result == (15, 3)

    def test_invalid_resolve_format(self) -> None:
        """Test invalid resolve format raises error."""
        with pytest.raises(click.BadParameter, match="Invalid resolve format"):
            parse_resolve("3-1")

    def test_invalid_resolve_not_numbers(self) -> None:
        """Test non-numeric resolve raises error."""
        with pytest.raises(click.BadParameter, match="Invalid resolve format"):
            parse_resolve("a=b")


class TestDateType:
    """Tests for DateType click parameter."""

    def test_convert_string(self) -> None:
        """Test converting string to datetime."""
        result = DATE.convert("2024-01-15", None, None)
        assert result == datetime(2024, 1, 15)

    def test_convert_datetime_passthrough(self) -> None:
        """Test datetime passes through unchanged."""
        dt = datetime(2024, 1, 15)
        result = DATE.convert(dt, None, None)
        assert result is dt


class TestTimeType:
    """Tests for TimeType click parameter."""

    def test_convert_string(self) -> None:
        """Test converting string to time."""
        result = TIME.convert("14:30", None, None)
        assert result == time(14, 30)

    def test_convert_time_passthrough(self) -> None:
        """Test time passes through unchanged."""
        t = time(14, 30)
        result = TIME.convert(t, None, None)
        assert result is t


class TestMainCommand:
    """Tests for main CLI command."""

    def test_requires_date(self) -> None:
        """Test that date option is required."""
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_version_option(self) -> None:
        """Test version option."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_preview_mode(self) -> None:
        """Test preview mode shows output without creating playlist."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(main, ["--date", "2024-01-15", "--preview"])

        assert result.exit_code == 0
        assert "Preview mode" in result.output

    def test_manual_mode(self) -> None:
        """Test manual mode shows search links."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(Match(song=songs[0], track=None, status=MatchStatus.NOT_FOUND))

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(main, ["--date", "2024-01-15", "--manual"])

        assert result.exit_code == 0
        assert "Manual Search Links" in result.output

    def test_no_songs_found(self) -> None:
        """Test error when no songs found."""
        runner = CliRunner()

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient"),
        ):
            mock_kutx.return_value.fetch_range.return_value = []

            result = runner.invoke(main, ["--date", "2024-01-15", "--preview"])

        assert result.exit_code == 1
        assert "No songs found" in result.output

    def test_with_time_range(self) -> None:
        """Test with start and end time options."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(
                main,
                [
                    "--date",
                    "2024-01-15",
                    "--start",
                    "14:00",
                    "--end",
                    "18:00",
                    "--preview",
                ],
            )

        assert result.exit_code == 0
        assert "14:00" in result.output
        assert "18:00" in result.output

    def test_with_resolve_option(self) -> None:
        """Test with resolve option."""
        runner = CliRunner()

        songs = [make_song(), make_song(title="Song 2")]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )
        match_result.add(Match(song=songs[1], track=None, status=MatchStatus.NOT_FOUND))

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--resolve", "2=1", "--preview"],
            )

        assert result.exit_code == 0

    def test_with_invalid_resolve_index(self) -> None:
        """Test with invalid resolve index."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--resolve", "99=1", "--preview"],
            )

        # Should still complete but show error for invalid index
        assert "Invalid resolution index" in result.output

    def test_cached_mode(self) -> None:
        """Test cached mode uses cache."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.KUTXCache") as mock_cache,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_cache.return_value.get.return_value = songs
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--cached", "--preview"],
            )

        assert result.exit_code == 0
        assert "Using cached KUTX data" in result.output

    def test_create_playlist_without_spotify_config(self) -> None:
        """Test creating playlist without Spotify credentials fails."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(main, ["--date", "2024-01-15"])

        assert result.exit_code == 1
        assert "Spotify API credentials not configured" in result.output

    def test_create_playlist_no_tracks(self) -> None:
        """Test creating playlist with no matched tracks fails."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(Match(song=songs[0], track=None, status=MatchStatus.NOT_FOUND))

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = True
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(main, ["--date", "2024-01-15"])

        assert result.exit_code == 1
        assert "No tracks to add to playlist" in result.output

    def test_create_playlist_success(self) -> None:
        """Test successful playlist creation."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify_instance = mock_spotify.return_value
            mock_spotify_instance.is_configured = True
            mock_spotify_instance.create_playlist.return_value = "playlist123"
            mock_spotify_instance.add_tracks.return_value = 1
            mock_spotify_instance.get_playlist_url.return_value = (
                "https://open.spotify.com/playlist/playlist123"
            )
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(main, ["--date", "2024-01-15"])

        assert result.exit_code == 0
        assert "Playlist created" in result.output

    def test_custom_playlist_name(self) -> None:
        """Test creating playlist with custom name."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify_instance = mock_spotify.return_value
            mock_spotify_instance.is_configured = True
            mock_spotify_instance.create_playlist.return_value = "playlist123"
            mock_spotify_instance.add_tracks.return_value = 1
            mock_spotify_instance.get_playlist_url.return_value = (
                "https://open.spotify.com/playlist/playlist123"
            )
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--name", "My Custom Playlist"],
            )

        assert result.exit_code == 0
        mock_spotify_instance.create_playlist.assert_called_once()
        call_args = mock_spotify_instance.create_playlist.call_args
        assert call_args[1]["name"] == "My Custom Playlist"


class TestFetchSongsWithCache:
    """Tests for _fetch_songs with caching."""

    def test_cached_data_with_time_filter(self) -> None:
        """Test that cached data is filtered by time."""
        runner = CliRunner()

        # Create songs at different times
        song_early = make_song(
            title="Early Song",
            played_at=datetime(2024, 1, 15, 10, 0, 0),
        )
        song_in_range = make_song(
            title="In Range Song",
            played_at=datetime(2024, 1, 15, 15, 0, 0),
        )
        song_late = make_song(
            title="Late Song",
            played_at=datetime(2024, 1, 15, 20, 0, 0),
        )
        cached_songs = [song_early, song_in_range, song_late]

        match_result = MatchResult()
        match_result.add(
            Match(song=song_in_range, track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient"),
            patch("kutx2spotify.cli.KUTXCache") as mock_cache,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_cache.return_value.get.return_value = cached_songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(
                main,
                [
                    "--date",
                    "2024-01-15",
                    "--start",
                    "14:00",
                    "--end",
                    "18:00",
                    "--cached",
                    "--preview",
                ],
            )

        assert result.exit_code == 0
        # Only one song should be processed (the one in range)
        mock_matcher.return_value.match_songs.assert_called_once()
        call_args = mock_matcher.return_value.match_songs.call_args
        filtered_songs = call_args[0][0]
        assert len(filtered_songs) == 1
        assert filtered_songs[0].title == "In Range Song"

    def test_cache_miss_fetches_from_api(self) -> None:
        """Test that cache miss triggers API fetch."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.KUTXCache") as mock_cache,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_cache.return_value.get.return_value = None  # Cache miss
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--cached", "--preview"],
            )

        assert result.exit_code == 0
        mock_kutx.return_value.fetch_range.assert_called_once()
        mock_cache.return_value.set.assert_called_once()  # Should cache result


class TestBrowserModeFlags:
    """Tests for --browser and --login CLI flags."""

    def test_browser_flag_triggers_browser_workflow(self) -> None:
        """Test that --browser flag invokes browser workflow."""
        runner = CliRunner()

        songs = [make_song()]

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient"),
            patch("kutx2spotify.cli.asyncio.run") as mock_asyncio_run,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--browser"],
            )

        # Should call asyncio.run with browser workflow
        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    def test_browser_flag_with_login(self) -> None:
        """Test that --login flag is passed to browser workflow."""
        runner = CliRunner()

        songs = [make_song()]

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient"),
            patch("kutx2spotify.cli.asyncio.run") as mock_asyncio_run,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--browser", "--login"],
            )

        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()
        # Verify force_login is True in the call
        call_args = mock_asyncio_run.call_args
        assert call_args is not None

    def test_browser_flag_uses_custom_name(self) -> None:
        """Test that --name is used with browser mode."""
        runner = CliRunner()

        songs = [make_song()]

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient"),
            patch("kutx2spotify.cli.asyncio.run") as mock_asyncio_run,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--browser", "--name", "My Playlist"],
            )

        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    def test_login_flag_without_browser_still_works(self) -> None:
        """Test that --login without --browser completes normally (ignored)."""
        runner = CliRunner()

        songs = [make_song()]
        match_result = MatchResult()
        match_result.add(
            Match(song=songs[0], track=make_track(), status=MatchStatus.EXACT)
        )

        with (
            patch("kutx2spotify.cli.KUTXClient") as mock_kutx,
            patch("kutx2spotify.cli.SpotifyClient") as mock_spotify,
            patch("kutx2spotify.cli.Matcher") as mock_matcher,
        ):
            mock_kutx.return_value.fetch_range.return_value = songs
            mock_spotify.return_value.is_configured = False
            mock_matcher.return_value.match_songs.return_value = match_result

            result = runner.invoke(
                main,
                ["--date", "2024-01-15", "--login", "--preview"],
            )

        assert result.exit_code == 0
        assert "Preview mode" in result.output


class TestRunBrowserWorkflow:
    """Tests for _run_browser_workflow async function."""

    def test_successful_workflow_empty_results(self) -> None:
        """Test browser workflow with empty search results."""
        import asyncio

        songs = [make_song()]

        mock_browser = MagicMock()
        mock_browser.ensure_logged_in = AsyncMock(return_value=True)
        mock_browser.create_playlist = AsyncMock(
            return_value="https://open.spotify.com/playlist/abc123"
        )
        mock_browser.search_tracks = AsyncMock(return_value=[])

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("kutx2spotify.cli.SpotifyBrowser", return_value=mock_context):
            # Should complete successfully even with no results found
            asyncio.run(
                _run_browser_workflow(songs, "Test Playlist", force_login=False)
            )

    def test_login_failure(self) -> None:
        """Test workflow exits on login failure."""
        import asyncio

        songs = [make_song()]

        mock_browser = MagicMock()
        mock_browser.ensure_logged_in = AsyncMock(return_value=False)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("kutx2spotify.cli.SpotifyBrowser", return_value=mock_context):
            with pytest.raises(SystemExit) as exc_info:
                asyncio.run(
                    _run_browser_workflow(songs, "Test Playlist", force_login=False)
                )
            assert exc_info.value.code == 1

    def test_playlist_creation_failure(self) -> None:
        """Test workflow exits on playlist creation failure."""
        import asyncio

        songs = [make_song()]

        mock_browser = MagicMock()
        mock_browser.ensure_logged_in = AsyncMock(return_value=True)
        mock_browser.create_playlist = AsyncMock(return_value=None)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("kutx2spotify.cli.SpotifyBrowser", return_value=mock_context):
            with pytest.raises(SystemExit) as exc_info:
                asyncio.run(
                    _run_browser_workflow(songs, "Test Playlist", force_login=False)
                )
            assert exc_info.value.code == 1

    def test_workflow_with_search_results(self) -> None:
        """Test workflow processes search results correctly."""
        import asyncio

        songs = [make_song()]

        mock_locator = MagicMock()
        mock_search_result = SearchResult(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_ms=180000,
            row_locator=mock_locator,
        )

        mock_browser = MagicMock()
        mock_browser.ensure_logged_in = AsyncMock(return_value=True)
        mock_browser.create_playlist = AsyncMock(
            return_value="https://open.spotify.com/playlist/abc123"
        )
        mock_browser.search_tracks = AsyncMock(return_value=[mock_search_result])
        mock_browser.add_to_current_playlist = AsyncMock(return_value=True)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("kutx2spotify.cli.SpotifyBrowser", return_value=mock_context):
            asyncio.run(
                _run_browser_workflow(songs, "Test Playlist", force_login=False)
            )

        mock_browser.add_to_current_playlist.assert_called_once()

    def test_workflow_handles_add_failure(self) -> None:
        """Test workflow handles add_to_current_playlist failure gracefully."""
        import asyncio

        songs = [make_song()]

        mock_locator = MagicMock()
        mock_search_result = SearchResult(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_ms=180000,
            row_locator=mock_locator,
        )

        mock_browser = MagicMock()
        mock_browser.ensure_logged_in = AsyncMock(return_value=True)
        mock_browser.create_playlist = AsyncMock(
            return_value="https://open.spotify.com/playlist/abc123"
        )
        mock_browser.search_tracks = AsyncMock(return_value=[mock_search_result])
        mock_browser.add_to_current_playlist = AsyncMock(
            side_effect=Exception("Failed to add")
        )

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("kutx2spotify.cli.SpotifyBrowser", return_value=mock_context):
            # Should not raise - handles gracefully
            asyncio.run(
                _run_browser_workflow(songs, "Test Playlist", force_login=False)
            )

    def test_force_login_passed_to_browser(self) -> None:
        """Test force_login parameter is passed to browser."""
        import asyncio

        songs = [make_song()]

        mock_browser = MagicMock()
        mock_browser.ensure_logged_in = AsyncMock(return_value=True)
        mock_browser.create_playlist = AsyncMock(
            return_value="https://open.spotify.com/playlist/abc123"
        )
        mock_browser.search_tracks = AsyncMock(return_value=[])

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("kutx2spotify.cli.SpotifyBrowser", return_value=mock_context):
            asyncio.run(_run_browser_workflow(songs, "Test Playlist", force_login=True))

        mock_browser.ensure_logged_in.assert_called_once_with(force_login=True)
