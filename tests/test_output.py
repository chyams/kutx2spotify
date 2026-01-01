"""Tests for output formatting module."""

from datetime import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console

from kutx2spotify.browser import SearchResult, SelectionResult
from kutx2spotify.models import Match, MatchResult, MatchStatus, Song, SpotifyTrack
from kutx2spotify.output import (
    format_duration,
    format_duration_diff,
    generate_spotify_search_url,
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
    print_warning,
)


def make_song(
    title: str = "Test Song",
    artist: str = "Test Artist",
    album: str = "Test Album",
    duration_ms: int = 180000,
) -> Song:
    """Create a test song."""
    return Song(
        title=title,
        artist=artist,
        album=album,
        duration_ms=duration_ms,
        played_at=datetime(2026, 1, 1, 14, 30, 0),
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


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_format_duration_basic(self) -> None:
        """Test basic duration formatting."""
        assert format_duration(180000) == "3:00"

    def test_format_duration_with_seconds(self) -> None:
        """Test duration with seconds."""
        assert format_duration(185000) == "3:05"

    def test_format_duration_long(self) -> None:
        """Test longer duration."""
        assert format_duration(600000) == "10:00"

    def test_format_duration_single_digit_seconds(self) -> None:
        """Test single digit seconds are zero-padded."""
        assert format_duration(63000) == "1:03"

    def test_format_duration_zero(self) -> None:
        """Test zero duration."""
        assert format_duration(0) == "0:00"


class TestFormatDurationDiff:
    """Tests for format_duration_diff function."""

    def test_positive_diff(self) -> None:
        """Test positive duration difference."""
        assert format_duration_diff(15000) == "+15s"

    def test_negative_diff(self) -> None:
        """Test negative duration difference."""
        assert format_duration_diff(-5000) == "-5s"

    def test_zero_diff(self) -> None:
        """Test zero duration difference."""
        assert format_duration_diff(0) == "+0s"


class TestGenerateSpotifySearchUrl:
    """Tests for generate_spotify_search_url function."""

    def test_basic_search_url(self) -> None:
        """Test basic search URL generation."""
        url = generate_spotify_search_url("Watermelon Man", "Herbie Hancock")
        assert "open.spotify.com/search" in url
        assert "Watermelon" in url or "watermelon" in url.lower()

    def test_search_url_encoding(self) -> None:
        """Test special characters are encoded."""
        url = generate_spotify_search_url("Don't Stop", "Artist")
        assert "%27" in url or "Don" in url  # URL encoded apostrophe or encoded


class TestPrintPlaylistHeader:
    """Tests for print_playlist_header function."""

    def test_header_with_date_only(self) -> None:
        """Test header with date only."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_playlist_header("2024-01-15")
        result = output.getvalue()
        assert "KUTX Playlist: 2024-01-15" in result

    def test_header_with_time_range(self) -> None:
        """Test header with start and end time."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_playlist_header("2024-01-15", "14:00", "18:00")
        result = output.getvalue()
        assert "2024-01-15" in result
        assert "14:00" in result
        assert "18:00" in result

    def test_header_with_start_only(self) -> None:
        """Test header with start time only."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_playlist_header("2024-01-15", start_time="14:00")
        result = output.getvalue()
        assert "14:00" in result
        assert "end of day" in result

    def test_header_with_end_only(self) -> None:
        """Test header with end time only."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_playlist_header("2024-01-15", end_time="18:00")
        result = output.getvalue()
        assert "start of day" in result
        assert "18:00" in result


class TestPrintMatchList:
    """Tests for print_match_list function."""

    def test_print_exact_match(self) -> None:
        """Test printing an exact match."""
        result = MatchResult()
        result.add(
            Match(song=make_song(), track=make_track(), status=MatchStatus.EXACT)
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_match_list(result)
        text = output.getvalue()
        assert "Test Song" in text
        assert "Test Artist" in text

    def test_print_match_with_issue(self) -> None:
        """Test printing a match with an issue shows asterisk."""
        result = MatchResult()
        result.add(Match(song=make_song(), track=None, status=MatchStatus.NOT_FOUND))

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_match_list(result)
        text = output.getvalue()
        assert "*" in text

    def test_print_multiple_matches(self) -> None:
        """Test printing multiple matches."""
        result = MatchResult()
        result.add(
            Match(
                song=make_song(title="Song 1"),
                track=make_track(),
                status=MatchStatus.EXACT,
            )
        )
        result.add(
            Match(
                song=make_song(title="Song 2"), track=None, status=MatchStatus.NOT_FOUND
            )
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_match_list(result)
        text = output.getvalue()
        assert "Song 1" in text
        assert "Song 2" in text


class TestPrintIssues:
    """Tests for print_issues function."""

    def test_no_issues(self) -> None:
        """Test with no issues prints nothing."""
        result = MatchResult()
        result.add(
            Match(song=make_song(), track=make_track(), status=MatchStatus.EXACT)
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_issues(result)
        text = output.getvalue()
        assert "ISSUES" not in text

    def test_not_found_issue(self) -> None:
        """Test printing NOT_FOUND issue."""
        result = MatchResult()
        result.add(Match(song=make_song(), track=None, status=MatchStatus.NOT_FOUND))

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_issues(result)
        text = output.getvalue()
        assert "ISSUES" in text
        assert "Not found on Spotify" in text

    def test_duration_mismatch_issue(self) -> None:
        """Test printing DURATION_MISMATCH issue."""
        result = MatchResult()
        song = make_song(duration_ms=180000)
        track = make_track(album="Different Album", duration_ms=195000)
        result.add(Match(song=song, track=track, status=MatchStatus.DURATION_MISMATCH))

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_issues(result)
        text = output.getvalue()
        assert "ISSUES" in text
        assert "Recommended" in text
        assert "--resolve" in text


class TestPrintManualLinks:
    """Tests for print_manual_links function."""

    def test_print_manual_links(self) -> None:
        """Test printing manual search links."""
        result = MatchResult()
        result.add(Match(song=make_song(), track=None, status=MatchStatus.NOT_FOUND))

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_manual_links(result)
        text = output.getvalue()
        assert "Manual Search Links" in text
        assert "open.spotify.com/search" in text


class TestPrintSummary:
    """Tests for print_summary function."""

    def test_summary_basic(self) -> None:
        """Test basic summary output."""
        result = MatchResult()
        result.add(
            Match(song=make_song(), track=make_track(), status=MatchStatus.EXACT)
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_summary(result)
        text = output.getvalue()
        assert "Total tracks: 1" in text
        assert "Matched: 1" in text

    def test_summary_preview_mode(self) -> None:
        """Test summary in preview mode."""
        result = MatchResult()
        result.add(
            Match(song=make_song(), track=make_track(), status=MatchStatus.EXACT)
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_summary(result, preview=True)
        text = output.getvalue()
        assert "Preview mode" in text

    def test_summary_with_issues(self) -> None:
        """Test summary showing issues count."""
        result = MatchResult()
        result.add(Match(song=make_song(), track=None, status=MatchStatus.NOT_FOUND))

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_summary(result)
        text = output.getvalue()
        assert "Issues: 1" in text


class TestPrintPlaylistCreated:
    """Tests for print_playlist_created function."""

    def test_playlist_created_output(self) -> None:
        """Test playlist created message."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_playlist_created(
                url="https://open.spotify.com/playlist/123",
                name="My Playlist",
                track_count=10,
            )
        text = output.getvalue()
        assert "Playlist created" in text
        assert "My Playlist" in text
        assert "10" in text
        assert "https://open.spotify.com/playlist/123" in text


class TestUtilityPrints:
    """Tests for utility print functions."""

    def test_print_error(self) -> None:
        """Test error printing."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_error("Something went wrong")
        text = output.getvalue()
        assert "Error: Something went wrong" in text

    def test_print_warning(self) -> None:
        """Test warning printing."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_warning("Be careful")
        text = output.getvalue()
        assert "Warning: Be careful" in text

    def test_print_info(self) -> None:
        """Test info printing."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_info("Here is some info")
        text = output.getvalue()
        assert "Here is some info" in text


def make_search_result(
    title: str = "Test Song",
    artist: str = "Test Artist",
    album: str = "Test Album",
    duration_ms: int = 180000,
) -> SearchResult:
    """Create a test search result."""
    mock_locator = MagicMock()
    return SearchResult(
        title=title,
        artist=artist,
        album=album,
        duration_ms=duration_ms,
        row_locator=mock_locator,
    )


class TestPrintBrowserHeader:
    """Tests for print_browser_header function."""

    def test_browser_header_basic(self) -> None:
        """Test basic browser header."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_header("KUTX 2025-12-31")
        text = output.getvalue()
        assert "Creating playlist: KUTX 2025-12-31 (private)" in text
        assert "Adding songs..." in text

    def test_browser_header_custom_name(self) -> None:
        """Test browser header with custom name."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_header("My Custom Playlist")
        text = output.getvalue()
        assert "My Custom Playlist" in text


class TestPrintBrowserTrackAdded:
    """Tests for print_browser_track_added function."""

    def test_exact_match(self) -> None:
        """Test printing exact match."""
        song = make_song()
        selected = make_search_result()
        selection = SelectionResult(
            selected=selected, reason="exact_match", alternatives=[]
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_track_added(1, song, selection)
        text = output.getvalue()
        assert "Test Song" in text
        assert "Test Artist" in text
        assert "[exact_match]" in text

    def test_album_match(self) -> None:
        """Test printing album match."""
        song = make_song(duration_ms=180000)
        selected = make_search_result(duration_ms=195000)  # +15s
        selection = SelectionResult(
            selected=selected, reason="album_match", alternatives=[]
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_track_added(1, song, selection)
        text = output.getvalue()
        assert "[album_match: +15s]" in text

    def test_duration_match(self) -> None:
        """Test printing duration match."""
        song = make_song(album="Original Album")
        selected = make_search_result(album="Different Album")
        selection = SelectionResult(
            selected=selected, reason="duration_match", alternatives=[]
        )

        output = StringIO()
        with patch(
            "kutx2spotify.output.console",
            Console(file=output, no_color=True, width=200),
        ):
            print_browser_track_added(1, song, selection)
        text = output.getvalue()
        assert "duration_match" in text
        assert "Different Album" in text
        assert "Original Album" in text

    def test_first_result(self) -> None:
        """Test printing first result fallback."""
        song = make_song()
        selected = make_search_result()
        selection = SelectionResult(
            selected=selected, reason="first_result", alternatives=[]
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_track_added(1, song, selection)
        text = output.getvalue()
        assert "[first_result]" in text

    def test_with_alternatives(self) -> None:
        """Test printing with alternatives shown."""
        song = make_song(duration_ms=180000)
        selected = make_search_result(album="Album 1")
        alt1 = make_search_result(album="Album 2", duration_ms=185000)
        alt2 = make_search_result(album="Album 3", duration_ms=190000)
        selection = SelectionResult(
            selected=selected, reason="album_match", alternatives=[alt1, alt2]
        )

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_track_added(1, song, selection)
        text = output.getvalue()
        assert "Other options:" in text
        assert "Album 2" in text
        assert "Album 3" in text

    def test_no_selected_track(self) -> None:
        """Test when no track is selected (early return)."""
        song = make_song()
        selection = SelectionResult(selected=None, reason="no_results", alternatives=[])

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_track_added(1, song, selection)
        text = output.getvalue()
        # Should not print anything
        assert text.strip() == ""


class TestPrintBrowserTrackSkipped:
    """Tests for print_browser_track_skipped function."""

    def test_skipped_no_results(self) -> None:
        """Test printing skipped track with no results."""
        song = make_song()

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_track_skipped(1, song, "no results")
        text = output.getvalue()
        assert "Test Song" in text
        assert "Test Artist" in text
        assert "[skipped: no results]" in text

    def test_skipped_failed_to_add(self) -> None:
        """Test printing skipped track that failed to add."""
        song = make_song(title="Obscure Song", artist="Unknown Artist")

        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_track_skipped(4, song, "failed to add")
        text = output.getvalue()
        assert "Obscure Song" in text
        assert "[skipped: failed to add]" in text
        assert "4." in text


class TestPrintBrowserSummary:
    """Tests for print_browser_summary function."""

    def test_summary_all_added(self) -> None:
        """Test summary when all tracks added."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_summary(
                added=10,
                skipped=0,
                playlist_url="https://open.spotify.com/playlist/abc123",
            )
        text = output.getvalue()
        assert "Summary:" in text
        assert "Added: 10/10" in text
        assert "Skipped: 0" in text
        assert "https://open.spotify.com/playlist/abc123" in text

    def test_summary_some_skipped(self) -> None:
        """Test summary with some tracks skipped."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_summary(
                added=7,
                skipped=3,
                playlist_url="https://open.spotify.com/playlist/xyz789",
            )
        text = output.getvalue()
        assert "Added: 7/10" in text
        assert "Skipped: 3" in text

    def test_summary_all_skipped(self) -> None:
        """Test summary when all tracks skipped."""
        output = StringIO()
        with patch("kutx2spotify.output.console", Console(file=output, no_color=True)):
            print_browser_summary(
                added=0,
                skipped=5,
                playlist_url="https://open.spotify.com/playlist/empty",
            )
        text = output.getvalue()
        assert "Added: 0/5" in text
        assert "Skipped: 5" in text
