"""Tests for the matching engine."""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kutx2spotify.cache import Resolution, ResolutionCache
from kutx2spotify.matcher import DURATION_TOLERANCE_MS, Matcher
from kutx2spotify.models import MatchResult, MatchStatus, Song, SpotifyTrack
from kutx2spotify.spotify import SpotifyClient


@pytest.fixture
def sample_song() -> Song:
    """Create a sample KUTX song for testing."""
    return Song(
        title="Watermelon Man",
        artist="Herbie Hancock",
        album="Head Hunters",
        duration_ms=252000,
        played_at=datetime(2026, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def sample_track() -> SpotifyTrack:
    """Create a sample Spotify track for testing."""
    return SpotifyTrack(
        id="track-123",
        uri="spotify:track:track-123",
        title="Watermelon Man",
        artist="Herbie Hancock",
        album="Head Hunters",
        duration_ms=252500,  # Within tolerance
        popularity=80,
    )


@pytest.fixture
def mock_spotify() -> MagicMock:
    """Create a mock SpotifyClient."""
    mock = MagicMock(spec=SpotifyClient)
    mock.is_configured = True
    return mock


@pytest.fixture
def resolution_cache(tmp_path: Path) -> ResolutionCache:
    """Create a resolution cache for testing."""
    cache_path = tmp_path / "resolutions.json"
    return ResolutionCache(cache_path=cache_path)


class TestMatcherInit:
    """Tests for Matcher initialization."""

    def test_init_with_spotify_client(self, mock_spotify: MagicMock) -> None:
        """Test Matcher initializes with SpotifyClient."""
        matcher = Matcher(spotify_client=mock_spotify)
        assert matcher._spotify is mock_spotify
        assert matcher._cache is None

    def test_init_with_resolution_cache(
        self, mock_spotify: MagicMock, resolution_cache: ResolutionCache
    ) -> None:
        """Test Matcher initializes with optional ResolutionCache."""
        matcher = Matcher(
            spotify_client=mock_spotify, resolution_cache=resolution_cache
        )
        assert matcher._spotify is mock_spotify
        assert matcher._cache is resolution_cache


class TestAlbumsMatch:
    """Tests for _albums_match helper."""

    def test_exact_match(self, mock_spotify: MagicMock) -> None:
        """Test exact album match."""
        matcher = Matcher(spotify_client=mock_spotify)
        assert matcher._albums_match("Head Hunters", "Head Hunters") is True

    def test_case_insensitive_match(self, mock_spotify: MagicMock) -> None:
        """Test case insensitive album match."""
        matcher = Matcher(spotify_client=mock_spotify)
        assert matcher._albums_match("Head Hunters", "head hunters") is True
        assert matcher._albums_match("HEAD HUNTERS", "Head Hunters") is True

    def test_no_match(self, mock_spotify: MagicMock) -> None:
        """Test albums don't match."""
        matcher = Matcher(spotify_client=mock_spotify)
        assert matcher._albums_match("Head Hunters", "Thrust") is False

    def test_empty_strings(self, mock_spotify: MagicMock) -> None:
        """Test empty album strings match."""
        matcher = Matcher(spotify_client=mock_spotify)
        assert matcher._albums_match("", "") is True


class TestDurationTolerance:
    """Tests for _is_within_duration_tolerance helper."""

    def test_within_tolerance(self, mock_spotify: MagicMock, sample_song: Song) -> None:
        """Test duration within tolerance."""
        matcher = Matcher(spotify_client=mock_spotify)
        track = SpotifyTrack(
            id="track-1",
            uri="spotify:track:track-1",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",
            duration_ms=sample_song.duration_ms + 5000,  # 5s difference
            popularity=80,
        )
        assert matcher._is_within_duration_tolerance(sample_song, track) is True

    def test_exactly_at_tolerance(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test duration exactly at tolerance boundary."""
        matcher = Matcher(spotify_client=mock_spotify)
        track = SpotifyTrack(
            id="track-1",
            uri="spotify:track:track-1",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",
            duration_ms=sample_song.duration_ms + DURATION_TOLERANCE_MS,
            popularity=80,
        )
        assert matcher._is_within_duration_tolerance(sample_song, track) is True

    def test_outside_tolerance(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test duration outside tolerance."""
        matcher = Matcher(spotify_client=mock_spotify)
        track = SpotifyTrack(
            id="track-1",
            uri="spotify:track:track-1",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",
            duration_ms=sample_song.duration_ms + 15000,  # 15s difference
            popularity=80,
        )
        assert matcher._is_within_duration_tolerance(sample_song, track) is False

    def test_negative_difference(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test shorter track within tolerance."""
        matcher = Matcher(spotify_client=mock_spotify)
        track = SpotifyTrack(
            id="track-1",
            uri="spotify:track:track-1",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",
            duration_ms=sample_song.duration_ms - 8000,  # 8s shorter
            popularity=80,
        )
        assert matcher._is_within_duration_tolerance(sample_song, track) is True


class TestFindExactMatch:
    """Tests for _find_exact_match helper."""

    def test_exact_match_found(
        self, mock_spotify: MagicMock, sample_song: Song, sample_track: SpotifyTrack
    ) -> None:
        """Test finding exact match with album."""
        mock_spotify.search_track.return_value = sample_track
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher._find_exact_match(sample_song)

        mock_spotify.search_track.assert_called_once_with(
            title=sample_song.title,
            artist=sample_song.artist,
            album=sample_song.album,
        )
        assert result is sample_track

    def test_no_match_found(self, mock_spotify: MagicMock, sample_song: Song) -> None:
        """Test no exact match found."""
        mock_spotify.search_track.return_value = None
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher._find_exact_match(sample_song)

        assert result is None

    def test_album_mismatch(self, mock_spotify: MagicMock, sample_song: Song) -> None:
        """Test album doesn't match despite search result."""
        track = SpotifyTrack(
            id="track-1",
            uri="spotify:track:track-1",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Different Album",  # Different album
            duration_ms=252000,
            popularity=80,
        )
        mock_spotify.search_track.return_value = track
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher._find_exact_match(sample_song)

        assert result is None


class TestFindBestFallback:
    """Tests for _find_best_fallback helper."""

    def test_finds_best_within_tolerance(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test finds best track within duration tolerance."""
        tracks = [
            SpotifyTrack(
                id="track-1",
                uri="spotify:track:track-1",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Live Album",
                duration_ms=sample_song.duration_ms + 5000,
                popularity=60,
            ),
            SpotifyTrack(
                id="track-2",
                uri="spotify:track:track-2",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Different Album",
                duration_ms=sample_song.duration_ms + 3000,
                popularity=90,  # Higher popularity
            ),
        ]
        mock_spotify.search_tracks.return_value = tracks
        matcher = Matcher(spotify_client=mock_spotify)

        result, within = matcher._find_best_fallback(sample_song)

        assert result is not None
        assert result.id == "track-2"  # Higher popularity
        assert within is True

    def test_falls_back_to_outside_tolerance(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test falls back to track outside tolerance if none within."""
        tracks = [
            SpotifyTrack(
                id="track-1",
                uri="spotify:track:track-1",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Live Album",
                duration_ms=sample_song.duration_ms + 30000,  # Way outside
                popularity=50,
            ),
            SpotifyTrack(
                id="track-2",
                uri="spotify:track:track-2",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Another Album",
                duration_ms=sample_song.duration_ms + 20000,  # Outside
                popularity=80,  # Higher popularity
            ),
        ]
        mock_spotify.search_tracks.return_value = tracks
        matcher = Matcher(spotify_client=mock_spotify)

        result, within = matcher._find_best_fallback(sample_song)

        assert result is not None
        assert result.id == "track-2"  # Higher popularity
        assert within is False

    def test_no_results(self, mock_spotify: MagicMock, sample_song: Song) -> None:
        """Test returns None when no results."""
        mock_spotify.search_tracks.return_value = []
        matcher = Matcher(spotify_client=mock_spotify)

        result, within = matcher._find_best_fallback(sample_song)

        assert result is None
        assert within is False

    def test_prefers_within_tolerance_over_popularity(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test prefers within tolerance even if lower popularity."""
        tracks = [
            SpotifyTrack(
                id="track-1",
                uri="spotify:track:track-1",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Album 1",
                duration_ms=sample_song.duration_ms + 5000,  # Within
                popularity=30,  # Lower
            ),
            SpotifyTrack(
                id="track-2",
                uri="spotify:track:track-2",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Album 2",
                duration_ms=sample_song.duration_ms + 20000,  # Outside
                popularity=100,  # Higher
            ),
        ]
        mock_spotify.search_tracks.return_value = tracks
        matcher = Matcher(spotify_client=mock_spotify)

        result, within = matcher._find_best_fallback(sample_song)

        assert result is not None
        assert result.id == "track-1"  # Prefers within tolerance
        assert within is True


class TestCheckResolutionCache:
    """Tests for _check_resolution_cache helper."""

    def test_no_cache(self, mock_spotify: MagicMock, sample_song: Song) -> None:
        """Test returns None when no cache configured."""
        matcher = Matcher(spotify_client=mock_spotify, resolution_cache=None)

        result = matcher._check_resolution_cache(sample_song)

        assert result is None

    def test_cache_miss(
        self,
        mock_spotify: MagicMock,
        sample_song: Song,
        resolution_cache: ResolutionCache,
    ) -> None:
        """Test returns None on cache miss."""
        matcher = Matcher(
            spotify_client=mock_spotify, resolution_cache=resolution_cache
        )

        result = matcher._check_resolution_cache(sample_song)

        assert result is None

    def test_cache_hit_exact(
        self,
        mock_spotify: MagicMock,
        sample_song: Song,
        resolution_cache: ResolutionCache,
    ) -> None:
        """Test returns Match with EXACT status on cache hit with matching album."""
        resolution = Resolution(
            spotify_uri="spotify:track:cached-123",
            resolved_album="Head Hunters",  # Same as song
            note="User verified",
        )
        resolution_cache.set(sample_song, resolution)
        matcher = Matcher(
            spotify_client=mock_spotify, resolution_cache=resolution_cache
        )

        result = matcher._check_resolution_cache(sample_song)

        assert result is not None
        assert result.status == MatchStatus.EXACT
        assert result.track is not None
        assert result.track.uri == "spotify:track:cached-123"

    def test_cache_hit_fallback(
        self,
        mock_spotify: MagicMock,
        sample_song: Song,
        resolution_cache: ResolutionCache,
    ) -> None:
        """Test returns Match with ALBUM_FALLBACK status when album differs."""
        resolution = Resolution(
            spotify_uri="spotify:track:cached-123",
            resolved_album="Different Album",  # Different from song
            note="User verified",
        )
        resolution_cache.set(sample_song, resolution)
        matcher = Matcher(
            spotify_client=mock_spotify, resolution_cache=resolution_cache
        )

        result = matcher._check_resolution_cache(sample_song)

        assert result is not None
        assert result.status == MatchStatus.ALBUM_FALLBACK
        assert result.track is not None


class TestMatchSong:
    """Tests for match_song method."""

    def test_exact_match(
        self, mock_spotify: MagicMock, sample_song: Song, sample_track: SpotifyTrack
    ) -> None:
        """Test exact match scenario."""
        mock_spotify.search_track.return_value = sample_track
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        assert result.status == MatchStatus.EXACT
        assert result.track is sample_track
        assert result.song is sample_song

    def test_exact_match_duration_mismatch(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test exact album match but duration outside tolerance."""
        track = SpotifyTrack(
            id="track-1",
            uri="spotify:track:track-1",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",
            duration_ms=sample_song.duration_ms + 30000,  # Way outside tolerance
            popularity=80,
        )
        mock_spotify.search_track.return_value = track
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        assert result.status == MatchStatus.DURATION_MISMATCH
        assert result.track is track

    def test_album_fallback(self, mock_spotify: MagicMock, sample_song: Song) -> None:
        """Test album fallback scenario."""
        mock_spotify.search_track.return_value = None
        fallback_track = SpotifyTrack(
            id="track-2",
            uri="spotify:track:track-2",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Different Album",  # Different album
            duration_ms=sample_song.duration_ms + 3000,  # Within tolerance
            popularity=70,
        )
        mock_spotify.search_tracks.return_value = [fallback_track]
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        assert result.status == MatchStatus.ALBUM_FALLBACK
        assert result.track is fallback_track

    def test_fallback_with_album_match(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test fallback that actually finds matching album."""
        mock_spotify.search_track.return_value = None
        # Fallback finds a track with matching album
        fallback_track = SpotifyTrack(
            id="track-2",
            uri="spotify:track:track-2",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",  # Same album
            duration_ms=sample_song.duration_ms + 3000,  # Within tolerance
            popularity=70,
        )
        mock_spotify.search_tracks.return_value = [fallback_track]
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        # Even from fallback, if album matches and duration is within tolerance, it's EXACT
        assert result.status == MatchStatus.EXACT
        assert result.track is fallback_track

    def test_fallback_duration_mismatch(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test fallback with duration outside tolerance."""
        mock_spotify.search_track.return_value = None
        fallback_track = SpotifyTrack(
            id="track-2",
            uri="spotify:track:track-2",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Different Album",
            duration_ms=sample_song.duration_ms + 30000,  # Way outside
            popularity=70,
        )
        mock_spotify.search_tracks.return_value = [fallback_track]
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        assert result.status == MatchStatus.DURATION_MISMATCH
        assert result.track is fallback_track

    def test_not_found(self, mock_spotify: MagicMock, sample_song: Song) -> None:
        """Test not found scenario."""
        mock_spotify.search_track.return_value = None
        mock_spotify.search_tracks.return_value = []
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        assert result.status == MatchStatus.NOT_FOUND
        assert result.track is None

    def test_cached_resolution_used(
        self,
        mock_spotify: MagicMock,
        sample_song: Song,
        resolution_cache: ResolutionCache,
    ) -> None:
        """Test cached resolution takes priority."""
        resolution = Resolution(
            spotify_uri="spotify:track:cached-123",
            resolved_album="Head Hunters",
            note="User verified",
        )
        resolution_cache.set(sample_song, resolution)
        matcher = Matcher(
            spotify_client=mock_spotify, resolution_cache=resolution_cache
        )

        result = matcher.match_song(sample_song)

        # Should not call Spotify API
        mock_spotify.search_track.assert_not_called()
        mock_spotify.search_tracks.assert_not_called()
        assert result.track is not None
        assert result.track.uri == "spotify:track:cached-123"


class TestMatchSongs:
    """Tests for match_songs batch method."""

    def test_matches_multiple_songs(self, mock_spotify: MagicMock) -> None:
        """Test batch matching multiple songs."""
        songs = [
            Song(
                title="Song 1",
                artist="Artist 1",
                album="Album 1",
                duration_ms=180000,
                played_at=datetime(2026, 1, 1, 12, 0, 0),
            ),
            Song(
                title="Song 2",
                artist="Artist 2",
                album="Album 2",
                duration_ms=200000,
                played_at=datetime(2026, 1, 1, 12, 5, 0),
            ),
        ]
        # First song found, second not found
        track1 = SpotifyTrack(
            id="track-1",
            uri="spotify:track:track-1",
            title="Song 1",
            artist="Artist 1",
            album="Album 1",
            duration_ms=182000,
            popularity=80,
        )
        mock_spotify.search_track.side_effect = [track1, None]
        mock_spotify.search_tracks.return_value = []

        matcher = Matcher(spotify_client=mock_spotify)
        result = matcher.match_songs(songs)

        assert result.total == 2
        assert result.found == 1
        assert result.not_found == 1
        assert result.exact_matches == 1

    def test_empty_song_list(self, mock_spotify: MagicMock) -> None:
        """Test batch matching with empty list."""
        matcher = Matcher(spotify_client=mock_spotify)
        result = matcher.match_songs([])

        assert result.total == 0
        assert result.found == 0
        assert result.not_found == 0

    def test_returns_match_result(self, mock_spotify: MagicMock) -> None:
        """Test returns MatchResult object."""
        matcher = Matcher(spotify_client=mock_spotify)
        result = matcher.match_songs([])

        assert isinstance(result, MatchResult)

    def test_graceful_when_spotify_not_configured(self) -> None:
        """Test graceful handling when Spotify is not configured."""
        with patch.dict(os.environ, {}, clear=True):
            spotify = SpotifyClient()
            matcher = Matcher(spotify_client=spotify)

            songs = [
                Song(
                    title="Test Song",
                    artist="Test Artist",
                    album="Test Album",
                    duration_ms=180000,
                    played_at=datetime(2026, 1, 1, 12, 0, 0),
                ),
            ]
            result = matcher.match_songs(songs)

            assert result.total == 1
            assert result.not_found == 1
            assert result.matches[0].status == MatchStatus.NOT_FOUND


class TestMatchSongEdgeCases:
    """Tests for edge cases in matching."""

    def test_fallback_with_matching_album_but_duration_mismatch(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test fallback finds album match but duration is off."""
        mock_spotify.search_track.return_value = None
        # Fallback finds track with same album but wrong duration
        fallback_track = SpotifyTrack(
            id="track-2",
            uri="spotify:track:track-2",
            title="Watermelon Man",
            artist="Herbie Hancock",
            album="Head Hunters",  # Same album
            duration_ms=sample_song.duration_ms + 30000,  # Way outside tolerance
            popularity=70,
        )
        mock_spotify.search_tracks.return_value = [fallback_track]
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        # Album matches but duration doesn't - should be DURATION_MISMATCH
        assert result.status == MatchStatus.DURATION_MISMATCH
        assert result.track is fallback_track

    def test_multiple_tracks_sorted_by_popularity(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test that among multiple within-tolerance tracks, highest popularity wins."""
        mock_spotify.search_track.return_value = None
        tracks = [
            SpotifyTrack(
                id="track-1",
                uri="spotify:track:track-1",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Album A",
                duration_ms=sample_song.duration_ms + 2000,
                popularity=50,
            ),
            SpotifyTrack(
                id="track-2",
                uri="spotify:track:track-2",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Album B",
                duration_ms=sample_song.duration_ms + 3000,
                popularity=95,  # Highest
            ),
            SpotifyTrack(
                id="track-3",
                uri="spotify:track:track-3",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Album C",
                duration_ms=sample_song.duration_ms + 1000,
                popularity=75,
            ),
        ]
        mock_spotify.search_tracks.return_value = tracks
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        assert result.track is not None
        assert result.track.id == "track-2"  # Highest popularity

    def test_all_tracks_outside_tolerance_picks_most_popular(
        self, mock_spotify: MagicMock, sample_song: Song
    ) -> None:
        """Test when all tracks outside tolerance, still picks most popular."""
        mock_spotify.search_track.return_value = None
        tracks = [
            SpotifyTrack(
                id="track-1",
                uri="spotify:track:track-1",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Album A",
                duration_ms=sample_song.duration_ms + 20000,
                popularity=40,
            ),
            SpotifyTrack(
                id="track-2",
                uri="spotify:track:track-2",
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Album B",
                duration_ms=sample_song.duration_ms + 25000,
                popularity=85,  # Highest
            ),
        ]
        mock_spotify.search_tracks.return_value = tracks
        matcher = Matcher(spotify_client=mock_spotify)

        result = matcher.match_song(sample_song)

        assert result.track is not None
        assert result.track.id == "track-2"
        assert result.status == MatchStatus.DURATION_MISMATCH


class TestDurationToleranceConstant:
    """Tests for duration tolerance constant."""

    def test_tolerance_is_10_seconds(self) -> None:
        """Test duration tolerance is 10 seconds (10000ms)."""
        assert DURATION_TOLERANCE_MS == 10_000
