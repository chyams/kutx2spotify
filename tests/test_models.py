"""Tests for data models."""

from datetime import datetime

from kutx2spotify.models import (
    Match,
    MatchResult,
    MatchStatus,
    Song,
    SpotifyTrack,
)


class TestSong:
    """Tests for Song dataclass."""

    def test_song_creation(self) -> None:
        """Test Song can be created with all fields."""
        song = Song(
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",
            duration_ms=252000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        assert song.title == "Watermelon Man"
        assert song.artist == "Herbie Hancock"
        assert song.album == "Head Hunters"
        assert song.duration_ms == 252000

    def test_duration_seconds(self) -> None:
        """Test duration_seconds property."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=252000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        assert song.duration_seconds == 252

    def test_duration_display(self) -> None:
        """Test duration_display formats correctly."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=252000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        assert song.duration_display() == "4:12"

    def test_duration_display_with_zero_seconds(self) -> None:
        """Test duration_display with exactly minute boundary."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=180000,  # 3:00
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        assert song.duration_display() == "3:00"

    def test_duration_display_with_single_digit_seconds(self) -> None:
        """Test duration_display pads single digit seconds."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=185000,  # 3:05
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        assert song.duration_display() == "3:05"


class TestSpotifyTrack:
    """Tests for SpotifyTrack dataclass."""

    def test_spotify_track_creation(self) -> None:
        """Test SpotifyTrack can be created with all fields."""
        track = SpotifyTrack(
            id="abc123",
            uri="spotify:track:abc123",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",
            duration_ms=252000,
        )
        assert track.id == "abc123"
        assert track.uri == "spotify:track:abc123"
        assert track.title == "Watermelon Man"
        assert track.artist == "Herbie Hancock"
        assert track.album == "Head Hunters"
        assert track.duration_ms == 252000
        assert track.popularity == 0  # Default value

    def test_spotify_track_with_popularity(self) -> None:
        """Test SpotifyTrack with explicit popularity."""
        track = SpotifyTrack(
            id="abc123",
            uri="spotify:track:abc123",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",
            duration_ms=252000,
            popularity=85,
        )
        assert track.popularity == 85


class TestMatchStatus:
    """Tests for MatchStatus enum."""

    def test_match_status_values(self) -> None:
        """Test MatchStatus enum values."""
        assert MatchStatus.EXACT.value == "exact"
        assert MatchStatus.ALBUM_FALLBACK.value == "album_fallback"
        assert MatchStatus.DURATION_MISMATCH.value == "duration_mismatch"
        assert MatchStatus.NOT_FOUND.value == "not_found"


class TestMatch:
    """Tests for Match dataclass."""

    def test_exact_match_no_issue(self) -> None:
        """Test exact match has no issue."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        track = SpotifyTrack(
            id="abc123",
            uri="spotify:track:abc123",
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=180000,
        )
        match = Match(song=song, track=track, status=MatchStatus.EXACT)
        assert not match.has_issue

    def test_album_fallback_no_issue(self) -> None:
        """Test album fallback has no issue."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        track = SpotifyTrack(
            id="abc123",
            uri="spotify:track:abc123",
            title="Test",
            artist="Artist",
            album="Different Album",
            duration_ms=180000,
        )
        match = Match(song=song, track=track, status=MatchStatus.ALBUM_FALLBACK)
        assert not match.has_issue

    def test_duration_mismatch_has_issue(self) -> None:
        """Test duration mismatch has issue."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        track = SpotifyTrack(
            id="abc123",
            uri="spotify:track:abc123",
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=300000,
        )
        match = Match(song=song, track=track, status=MatchStatus.DURATION_MISMATCH)
        assert match.has_issue

    def test_not_found_has_issue(self) -> None:
        """Test not found has issue."""
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        match = Match(song=song, track=None, status=MatchStatus.NOT_FOUND)
        assert match.has_issue


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_empty_result(self) -> None:
        """Test empty MatchResult."""
        result = MatchResult()
        assert result.total == 0
        assert result.found == 0
        assert result.not_found == 0
        assert result.exact_matches == 0
        assert result.issues == []

    def test_add_match(self) -> None:
        """Test adding a match."""
        result = MatchResult()
        song = Song(
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        track = SpotifyTrack(
            id="abc123",
            uri="spotify:track:abc123",
            title="Test",
            artist="Artist",
            album="Album",
            duration_ms=180000,
        )
        match = Match(song=song, track=track, status=MatchStatus.EXACT)
        result.add(match)
        assert result.total == 1

    def test_aggregation(self) -> None:
        """Test aggregation properties."""
        result = MatchResult()

        # Add exact match
        song1 = Song(
            title="Test1",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            played_at=datetime(2026, 1, 1, 14, 30, 0),
        )
        track1 = SpotifyTrack(
            id="abc123",
            uri="spotify:track:abc123",
            title="Test1",
            artist="Artist",
            album="Album",
            duration_ms=180000,
        )
        result.add(Match(song=song1, track=track1, status=MatchStatus.EXACT))

        # Add duration mismatch
        song2 = Song(
            title="Test2",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            played_at=datetime(2026, 1, 1, 14, 35, 0),
        )
        track2 = SpotifyTrack(
            id="def456",
            uri="spotify:track:def456",
            title="Test2",
            artist="Artist",
            album="Album",
            duration_ms=300000,
        )
        result.add(
            Match(song=song2, track=track2, status=MatchStatus.DURATION_MISMATCH)
        )

        # Add not found
        song3 = Song(
            title="Test3",
            artist="Artist",
            album="Album",
            duration_ms=180000,
            played_at=datetime(2026, 1, 1, 14, 40, 0),
        )
        result.add(Match(song=song3, track=None, status=MatchStatus.NOT_FOUND))

        assert result.total == 3
        assert result.found == 2
        assert result.not_found == 1
        assert result.exact_matches == 1
        assert len(result.issues) == 2
