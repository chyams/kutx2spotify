"""Tests for output formatting module."""

from datetime import datetime
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from kutx2spotify.models import Match, MatchResult, MatchStatus, Song, SpotifyTrack
from kutx2spotify.output import (
    format_duration,
    format_duration_diff,
    generate_spotify_search_url,
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
