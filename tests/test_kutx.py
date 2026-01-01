"""Tests for KUTX API client."""

from datetime import datetime, time
from unittest.mock import Mock, patch

import httpx
import pytest

from kutx2spotify.kutx import KUTXClient

SAMPLE_KUTX_RESPONSE = {
    "playlist": [
        {
            "_start_time": "01-01-2026 14:30:00",
            "trackName": "Watermelon Man",
            "artistName": "Herbie Hancock",
            "collectionName": "Head Hunters",
            "_duration": 252000,
        },
        {
            "_start_time": "01-01-2026 14:35:00",
            "trackName": "Chameleon",
            "artistName": "Herbie Hancock",
            "collectionName": "Head Hunters",
            "_duration": 900000,
        },
        {
            "_start_time": "01-01-2026 16:00:00",
            "trackName": "So What",
            "artistName": "Miles Davis",
            "collectionName": "Kind of Blue",
            "_duration": 545000,
        },
    ]
}


class TestKUTXClientParsing:
    """Tests for KUTX client parsing logic."""

    def test_parse_song_valid(self) -> None:
        """Test parsing a valid song."""
        client = KUTXClient()
        track_data = {
            "_start_time": "01-01-2026 14:30:00",
            "trackName": "Watermelon Man",
            "artistName": "Herbie Hancock",
            "collectionName": "Head Hunters",
            "_duration": 252000,
        }
        song = client._parse_song(track_data)

        assert song is not None
        assert song.title == "Watermelon Man"
        assert song.artist == "Herbie Hancock"
        assert song.album == "Head Hunters"
        assert song.duration_ms == 252000
        assert song.played_at == datetime(2026, 1, 1, 14, 30, 0)

    def test_parse_song_missing_title(self) -> None:
        """Test parsing song with missing title returns None."""
        client = KUTXClient()
        track_data = {
            "_start_time": "01-01-2026 14:30:00",
            "artistName": "Herbie Hancock",
            "collectionName": "Head Hunters",
            "_duration": 252000,
        }
        song = client._parse_song(track_data)
        assert song is None

    def test_parse_song_missing_artist(self) -> None:
        """Test parsing song with missing artist returns None."""
        client = KUTXClient()
        track_data = {
            "_start_time": "01-01-2026 14:30:00",
            "trackName": "Watermelon Man",
            "collectionName": "Head Hunters",
            "_duration": 252000,
        }
        song = client._parse_song(track_data)
        assert song is None

    def test_parse_song_missing_start_time(self) -> None:
        """Test parsing song with missing start time returns None."""
        client = KUTXClient()
        track_data = {
            "trackName": "Watermelon Man",
            "artistName": "Herbie Hancock",
            "collectionName": "Head Hunters",
            "_duration": 252000,
        }
        song = client._parse_song(track_data)
        assert song is None

    def test_parse_song_invalid_start_time_format(self) -> None:
        """Test parsing song with invalid start time format returns None."""
        client = KUTXClient()
        track_data = {
            "_start_time": "2026-01-01 14:30:00",  # Wrong format
            "trackName": "Watermelon Man",
            "artistName": "Herbie Hancock",
            "collectionName": "Head Hunters",
            "_duration": 252000,
        }
        song = client._parse_song(track_data)
        assert song is None

    def test_parse_song_missing_album_uses_empty_string(self) -> None:
        """Test parsing song with missing album uses empty string."""
        client = KUTXClient()
        track_data = {
            "_start_time": "01-01-2026 14:30:00",
            "trackName": "Watermelon Man",
            "artistName": "Herbie Hancock",
            "_duration": 252000,
        }
        song = client._parse_song(track_data)

        assert song is not None
        assert song.album == ""

    def test_parse_song_missing_duration_uses_zero(self) -> None:
        """Test parsing song with missing duration uses zero."""
        client = KUTXClient()
        track_data = {
            "_start_time": "01-01-2026 14:30:00",
            "trackName": "Watermelon Man",
            "artistName": "Herbie Hancock",
            "collectionName": "Head Hunters",
        }
        song = client._parse_song(track_data)

        assert song is not None
        assert song.duration_ms == 0

    def test_parse_song_empty_title(self) -> None:
        """Test parsing song with empty title returns None."""
        client = KUTXClient()
        track_data = {
            "_start_time": "01-01-2026 14:30:00",
            "trackName": "",
            "artistName": "Herbie Hancock",
            "collectionName": "Head Hunters",
            "_duration": 252000,
        }
        song = client._parse_song(track_data)
        assert song is None

    def test_parse_song_empty_artist(self) -> None:
        """Test parsing song with empty artist returns None."""
        client = KUTXClient()
        track_data = {
            "_start_time": "01-01-2026 14:30:00",
            "trackName": "Watermelon Man",
            "artistName": "",
            "collectionName": "Head Hunters",
            "_duration": 252000,
        }
        song = client._parse_song(track_data)
        assert song is None


class TestKUTXClientFetchDay:
    """Tests for fetch_day method."""

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_day_success(self, mock_client_class: Mock) -> None:
        """Test fetching day returns parsed songs."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_KUTX_RESPONSE
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_day(datetime(2026, 1, 1))

        assert len(songs) == 3
        assert songs[0].title == "Watermelon Man"
        assert songs[1].title == "Chameleon"
        assert songs[2].title == "So What"

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_day_empty_playlist(self, mock_client_class: Mock) -> None:
        """Test fetching day with empty playlist."""
        mock_response = Mock()
        mock_response.json.return_value = {"playlist": []}
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_day(datetime(2026, 1, 1))

        assert len(songs) == 0

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_day_missing_playlist_key(self, mock_client_class: Mock) -> None:
        """Test fetching day with missing playlist key."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_day(datetime(2026, 1, 1))

        assert len(songs) == 0

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_day_filters_invalid_songs(self, mock_client_class: Mock) -> None:
        """Test fetching day filters out invalid songs."""
        response_with_invalid = {
            "playlist": [
                {
                    "_start_time": "01-01-2026 14:30:00",
                    "trackName": "Valid Song",
                    "artistName": "Artist",
                    "collectionName": "Album",
                    "_duration": 180000,
                },
                {
                    # Missing trackName
                    "_start_time": "01-01-2026 14:35:00",
                    "artistName": "Artist",
                    "collectionName": "Album",
                    "_duration": 180000,
                },
            ]
        }

        mock_response = Mock()
        mock_response.json.return_value = response_with_invalid
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_day(datetime(2026, 1, 1))

        assert len(songs) == 1
        assert songs[0].title == "Valid Song"

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_day_api_error(self, mock_client_class: Mock) -> None:
        """Test fetching day raises on API error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=Mock()
        )

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()

        with pytest.raises(httpx.HTTPStatusError):
            client.fetch_day(datetime(2026, 1, 1))

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_day_passes_correct_params(self, mock_client_class: Mock) -> None:
        """Test fetch_day passes correct params to API."""
        mock_response = Mock()
        mock_response.json.return_value = {"playlist": []}
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        client.fetch_day(datetime(2026, 1, 15))

        mock_client_instance.get.assert_called_once()
        call_args = mock_client_instance.get.call_args
        assert call_args[1]["params"]["date"] == "2026-01-15"
        assert call_args[1]["params"]["format"] == "json"


class TestKUTXClientFetchRange:
    """Tests for fetch_range method."""

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_range_no_filters(self, mock_client_class: Mock) -> None:
        """Test fetch_range with no time filters returns all songs."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_KUTX_RESPONSE
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_range(datetime(2026, 1, 1))

        assert len(songs) == 3

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_range_with_start_time(self, mock_client_class: Mock) -> None:
        """Test fetch_range with start_time filter."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_KUTX_RESPONSE
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_range(datetime(2026, 1, 1), start_time=time(15, 0))

        assert len(songs) == 1
        assert songs[0].title == "So What"

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_range_with_end_time(self, mock_client_class: Mock) -> None:
        """Test fetch_range with end_time filter."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_KUTX_RESPONSE
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_range(datetime(2026, 1, 1), end_time=time(15, 0))

        assert len(songs) == 2
        assert songs[0].title == "Watermelon Man"
        assert songs[1].title == "Chameleon"

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_range_with_both_times(self, mock_client_class: Mock) -> None:
        """Test fetch_range with both start and end time filters."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_KUTX_RESPONSE
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_range(
            datetime(2026, 1, 1),
            start_time=time(14, 30),
            end_time=time(14, 35),
        )

        assert len(songs) == 2
        assert songs[0].title == "Watermelon Man"
        assert songs[1].title == "Chameleon"

    @patch("kutx2spotify.kutx.httpx.Client")
    def test_fetch_range_no_matches(self, mock_client_class: Mock) -> None:
        """Test fetch_range with no matches in range."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_KUTX_RESPONSE
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client_instance

        client = KUTXClient()
        songs = client.fetch_range(
            datetime(2026, 1, 1),
            start_time=time(20, 0),
            end_time=time(21, 0),
        )

        assert len(songs) == 0


class TestKUTXClientInit:
    """Tests for KUTXClient initialization."""

    def test_default_base_url(self) -> None:
        """Test client uses default base URL."""
        client = KUTXClient()
        assert "api.composer.nprstations.org" in client.base_url

    def test_custom_base_url(self) -> None:
        """Test client accepts custom base URL."""
        client = KUTXClient(base_url="https://custom.api.com/playlist")
        assert client.base_url == "https://custom.api.com/playlist"
