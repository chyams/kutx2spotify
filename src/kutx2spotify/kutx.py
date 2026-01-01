"""KUTX API client for fetching playlist data."""

from datetime import datetime, time
from typing import Any

import httpx

from kutx2spotify.models import Song

KUTX_API_URL = (
    "https://api.composer.nprstations.org/v1/widget/50ef24ebe1c8a1369593d032/day"
)


class KUTXClient:
    """Client for fetching KUTX playlist data."""

    def __init__(self, base_url: str = KUTX_API_URL) -> None:
        """Initialize the KUTX client.

        Args:
            base_url: Base URL for the KUTX API.
        """
        self.base_url = base_url

    def _parse_song(self, track_data: dict[str, Any]) -> Song | None:
        """Parse a song from API response data.

        Args:
            track_data: Raw track data from the API.

        Returns:
            Parsed Song or None if essential fields are missing.
        """
        title = track_data.get("trackName")
        artist = track_data.get("artistName")

        if not title or not artist:
            return None

        album = track_data.get("collectionName", "")
        duration_ms = track_data.get("_duration", 0)

        # Parse start time: "MM-DD-YYYY HH:MM:SS"
        start_time_str = track_data.get("_start_time", "")
        if not start_time_str:
            return None

        try:
            played_at = datetime.strptime(start_time_str, "%m-%d-%Y %H:%M:%S")
        except ValueError:
            return None

        return Song(
            title=title,
            artist=artist,
            album=album,
            duration_ms=duration_ms,
            played_at=played_at,
        )

    def fetch_day(self, date: datetime) -> list[Song]:
        """Fetch all songs played on a given date.

        Args:
            date: The date to fetch playlist for.

        Returns:
            List of songs played on that date.
        """
        params = {
            "date": date.strftime("%Y-%m-%d"),
            "format": "json",
        }

        with httpx.Client() as client:
            response = client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

        playlist = data.get("playlist", [])
        songs: list[Song] = []

        for track_data in playlist:
            song = self._parse_song(track_data)
            if song is not None:
                songs.append(song)

        return songs

    def fetch_range(
        self,
        date: datetime,
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> list[Song]:
        """Fetch songs within a time range on a given date.

        Args:
            date: The date to fetch playlist for.
            start_time: Start of time range (inclusive). None means start of day.
            end_time: End of time range (inclusive). None means end of day.

        Returns:
            List of songs played within the time range.
        """
        songs = self.fetch_day(date)

        if start_time is None and end_time is None:
            return songs

        filtered: list[Song] = []
        for song in songs:
            song_time = song.played_at.time()

            if start_time is not None and song_time < start_time:
                continue

            if end_time is not None and song_time > end_time:
                continue

            filtered.append(song)

        return filtered
