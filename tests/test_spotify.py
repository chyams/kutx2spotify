"""Tests for Spotify client."""

import os
from unittest.mock import MagicMock, patch

import pytest

from kutx2spotify.spotify import (
    SPOTIFY_ADD_TRACKS_LIMIT,
    SPOTIFY_ENV_VARS,
    SpotifyClient,
    SpotifyNotConfiguredError,
)


class TestSpotifyNotConfiguredError:
    """Tests for SpotifyNotConfiguredError."""

    def test_error_message_lists_missing_vars(self) -> None:
        """Test error message lists missing environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            error = SpotifyNotConfiguredError()
            message = str(error)

            assert "Spotify API credentials not configured" in message
            for var in SPOTIFY_ENV_VARS:
                assert var in message

    def test_error_message_partial_config(self) -> None:
        """Test error message with partial configuration."""
        env = {"SPOTIPY_CLIENT_ID": "test-id"}
        with patch.dict(os.environ, env, clear=True):
            error = SpotifyNotConfiguredError()
            message = str(error)

            assert "SPOTIPY_CLIENT_ID" not in message
            assert "SPOTIPY_CLIENT_SECRET" in message
            assert "SPOTIPY_REDIRECT_URI" in message


class TestSpotifyClientIsConfigured:
    """Tests for is_configured property."""

    def test_is_configured_all_vars_set(self) -> None:
        """Test is_configured returns True when all vars set."""
        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            assert client.is_configured is True

    def test_is_configured_missing_all_vars(self) -> None:
        """Test is_configured returns False when no vars set."""
        with patch.dict(os.environ, {}, clear=True):
            client = SpotifyClient()
            assert client.is_configured is False

    def test_is_configured_missing_one_var(self) -> None:
        """Test is_configured returns False when one var missing."""
        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            # Missing SPOTIPY_REDIRECT_URI
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            assert client.is_configured is False

    def test_is_configured_empty_value(self) -> None:
        """Test is_configured returns False with empty value."""
        env = {
            "SPOTIPY_CLIENT_ID": "",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            assert client.is_configured is False


class TestSpotifyClientGetClient:
    """Tests for _get_client method."""

    def test_get_client_raises_when_not_configured(self) -> None:
        """Test _get_client raises SpotifyNotConfiguredError."""
        with patch.dict(os.environ, {}, clear=True):
            client = SpotifyClient()
            with pytest.raises(SpotifyNotConfiguredError):
                client._get_client()

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_get_client_creates_client(
        self,
        mock_spotify: MagicMock,
        mock_oauth: MagicMock,
    ) -> None:
        """Test _get_client creates authenticated client."""
        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client._get_client()

            mock_oauth.assert_called_once_with(
                scope="playlist-modify-public playlist-modify-private"
            )
            mock_spotify.assert_called_once_with(auth_manager=mock_oauth.return_value)
            assert result == mock_spotify.return_value

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_get_client_caches_client(
        self,
        mock_spotify: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test _get_client caches and reuses client."""
        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            first_call = client._get_client()
            second_call = client._get_client()

            assert first_call is second_call
            assert mock_spotify.call_count == 1


class TestSpotifyClientSearchTrack:
    """Tests for search_track method."""

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_search_track_with_album(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test search_track builds correct query with album."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "track-id",
                        "uri": "spotify:track:track-id",
                        "name": "Watermelon Man",
                        "artists": [{"name": "Herbie Hancock"}],
                        "album": {"name": "Head Hunters"},
                        "duration_ms": 252000,
                    }
                ]
            }
        }
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.search_track(
                title="Watermelon Man",
                artist="Herbie Hancock",
                album="Head Hunters",
            )

            mock_client.search.assert_called_once_with(
                q='track:"Watermelon Man" artist:"Herbie Hancock" album:"Head Hunters"',
                type="track",
                limit=1,
            )

            assert result is not None
            assert result.id == "track-id"
            assert result.uri == "spotify:track:track-id"
            assert result.title == "Watermelon Man"
            assert result.artist == "Herbie Hancock"
            assert result.album == "Head Hunters"
            assert result.duration_ms == 252000

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_search_track_without_album(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test search_track builds correct query without album."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "track-id",
                        "uri": "spotify:track:track-id",
                        "name": "So What",
                        "artists": [{"name": "Miles Davis"}],
                        "album": {"name": "Kind of Blue"},
                        "duration_ms": 545000,
                    }
                ]
            }
        }
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.search_track(
                title="So What",
                artist="Miles Davis",
            )

            mock_client.search.assert_called_once_with(
                q='track:"So What" artist:"Miles Davis"',
                type="track",
                limit=1,
            )

            assert result is not None
            assert result.title == "So What"

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_search_track_not_found(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test search_track returns None when not found."""
        mock_client = MagicMock()
        mock_client.search.return_value = {"tracks": {"items": []}}
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.search_track(
                title="Nonexistent Song",
                artist="Unknown Artist",
            )

            assert result is None

    def test_search_track_raises_when_not_configured(self) -> None:
        """Test search_track raises SpotifyNotConfiguredError."""
        with patch.dict(os.environ, {}, clear=True):
            client = SpotifyClient()
            with pytest.raises(SpotifyNotConfiguredError):
                client.search_track(title="Test", artist="Test")

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_search_track_empty_tracks_dict(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test search_track handles empty tracks dict."""
        mock_client = MagicMock()
        mock_client.search.return_value = {}
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.search_track(title="Test", artist="Test")

            assert result is None

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_search_track_missing_artists(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test search_track handles track with no artists."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "track-id",
                        "uri": "spotify:track:track-id",
                        "name": "Test Track",
                        "artists": [],
                        "album": {"name": "Test Album"},
                        "duration_ms": 180000,
                    }
                ]
            }
        }
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.search_track(title="Test", artist="Test")

            assert result is not None
            assert result.artist == ""

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_search_track_missing_album(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test search_track handles track with no album."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "track-id",
                        "uri": "spotify:track:track-id",
                        "name": "Test Track",
                        "artists": [{"name": "Artist"}],
                        "duration_ms": 180000,
                    }
                ]
            }
        }
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.search_track(title="Test", artist="Test")

            assert result is not None
            assert result.album == ""


class TestSpotifyClientSearchTrackLoose:
    """Tests for search_track_loose method."""

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_search_track_loose_no_album(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test search_track_loose searches without album."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "tracks": {
                "items": [
                    {
                        "id": "track-id",
                        "uri": "spotify:track:track-id",
                        "name": "Chameleon",
                        "artists": [{"name": "Herbie Hancock"}],
                        "album": {"name": "Head Hunters"},
                        "duration_ms": 900000,
                    }
                ]
            }
        }
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.search_track_loose(
                title="Chameleon",
                artist="Herbie Hancock",
            )

            mock_client.search.assert_called_once_with(
                q='track:"Chameleon" artist:"Herbie Hancock"',
                type="track",
                limit=1,
            )

            assert result is not None
            assert result.title == "Chameleon"


class TestSpotifyClientCreatePlaylist:
    """Tests for create_playlist method."""

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_create_playlist_public(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test create_playlist creates public playlist."""
        mock_client = MagicMock()
        mock_client.current_user.return_value = {"id": "user-123"}
        mock_client.user_playlist_create.return_value = {"id": "playlist-id"}
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.create_playlist(
                name="KUTX 2026-01-01",
                description="Tracks from KUTX",
                public=True,
            )

            mock_client.user_playlist_create.assert_called_once_with(
                user="user-123",
                name="KUTX 2026-01-01",
                public=True,
                description="Tracks from KUTX",
            )
            assert result == "playlist-id"

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_create_playlist_private(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test create_playlist creates private playlist."""
        mock_client = MagicMock()
        mock_client.current_user.return_value = {"id": "user-123"}
        mock_client.user_playlist_create.return_value = {"id": "private-playlist"}
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.create_playlist(
                name="Private Playlist",
                public=False,
            )

            mock_client.user_playlist_create.assert_called_once_with(
                user="user-123",
                name="Private Playlist",
                public=False,
                description="",
            )
            assert result == "private-playlist"

    def test_create_playlist_raises_when_not_configured(self) -> None:
        """Test create_playlist raises SpotifyNotConfiguredError."""
        with patch.dict(os.environ, {}, clear=True):
            client = SpotifyClient()
            with pytest.raises(SpotifyNotConfiguredError):
                client.create_playlist(name="Test")


class TestSpotifyClientAddTracks:
    """Tests for add_tracks method."""

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_add_tracks_single_batch(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test add_tracks adds tracks in single batch."""
        mock_client = MagicMock()
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            track_uris = [f"spotify:track:{i}" for i in range(50)]
            result = client.add_tracks("playlist-id", track_uris)

            mock_client.playlist_add_items.assert_called_once_with(
                "playlist-id", track_uris
            )
            assert result == 50

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_add_tracks_multiple_batches(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test add_tracks batches when over 100 tracks."""
        mock_client = MagicMock()
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            track_uris = [f"spotify:track:{i}" for i in range(250)]
            result = client.add_tracks("playlist-id", track_uris)

            # Should be called 3 times: 100 + 100 + 50
            assert mock_client.playlist_add_items.call_count == 3

            # Verify batch sizes
            calls = mock_client.playlist_add_items.call_args_list
            assert len(calls[0][0][1]) == SPOTIFY_ADD_TRACKS_LIMIT
            assert len(calls[1][0][1]) == SPOTIFY_ADD_TRACKS_LIMIT
            assert len(calls[2][0][1]) == 50

            assert result == 250

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_add_tracks_empty_list(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test add_tracks with empty list."""
        mock_client = MagicMock()
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            result = client.add_tracks("playlist-id", [])

            mock_client.playlist_add_items.assert_not_called()
            assert result == 0

    @patch("kutx2spotify.spotify.SpotifyOAuth")
    @patch("kutx2spotify.spotify.spotipy.Spotify")
    def test_add_tracks_exactly_100(
        self,
        mock_spotify_class: MagicMock,
        _mock_oauth: MagicMock,
    ) -> None:
        """Test add_tracks with exactly 100 tracks."""
        mock_client = MagicMock()
        mock_spotify_class.return_value = mock_client

        env = {
            "SPOTIPY_CLIENT_ID": "test-id",
            "SPOTIPY_CLIENT_SECRET": "test-secret",
            "SPOTIPY_REDIRECT_URI": "http://localhost:8888/callback",
        }
        with patch.dict(os.environ, env, clear=True):
            client = SpotifyClient()
            track_uris = [f"spotify:track:{i}" for i in range(100)]
            result = client.add_tracks("playlist-id", track_uris)

            mock_client.playlist_add_items.assert_called_once()
            assert result == 100

    def test_add_tracks_raises_when_not_configured(self) -> None:
        """Test add_tracks raises SpotifyNotConfiguredError."""
        with patch.dict(os.environ, {}, clear=True):
            client = SpotifyClient()
            with pytest.raises(SpotifyNotConfiguredError):
                client.add_tracks("playlist-id", ["spotify:track:1"])


class TestSpotifyClientGetPlaylistUrl:
    """Tests for get_playlist_url method."""

    def test_get_playlist_url(self) -> None:
        """Test get_playlist_url returns correct URL."""
        client = SpotifyClient()
        url = client.get_playlist_url("abc123xyz")
        assert url == "https://open.spotify.com/playlist/abc123xyz"

    def test_get_playlist_url_special_chars(self) -> None:
        """Test get_playlist_url with various playlist IDs."""
        client = SpotifyClient()
        url = client.get_playlist_url("1a2B3c4D5e6F7g8H9i0J")
        assert url == "https://open.spotify.com/playlist/1a2B3c4D5e6F7g8H9i0J"


class TestSpotifyClientParseTrack:
    """Tests for _parse_track method."""

    def test_parse_track_complete_data(self) -> None:
        """Test _parse_track with complete data."""
        client = SpotifyClient()
        track_data = {
            "id": "track-id",
            "uri": "spotify:track:track-id",
            "name": "Test Track",
            "artists": [{"name": "Test Artist"}],
            "album": {"name": "Test Album"},
            "duration_ms": 180000,
        }

        result = client._parse_track(track_data)

        assert result.id == "track-id"
        assert result.uri == "spotify:track:track-id"
        assert result.title == "Test Track"
        assert result.artist == "Test Artist"
        assert result.album == "Test Album"
        assert result.duration_ms == 180000

    def test_parse_track_missing_duration(self) -> None:
        """Test _parse_track with missing duration."""
        client = SpotifyClient()
        track_data = {
            "id": "track-id",
            "uri": "spotify:track:track-id",
            "name": "Test Track",
            "artists": [{"name": "Test Artist"}],
            "album": {"name": "Test Album"},
        }

        result = client._parse_track(track_data)

        assert result.duration_ms == 0
