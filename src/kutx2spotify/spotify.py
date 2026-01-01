"""Spotify API client for playlist creation and track search."""

import os
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from kutx2spotify.models import SpotifyTrack

# Environment variables required for Spotify API
SPOTIFY_ENV_VARS = (
    "SPOTIPY_CLIENT_ID",
    "SPOTIPY_CLIENT_SECRET",
    "SPOTIPY_REDIRECT_URI",
)

# Spotify API limits
SPOTIFY_ADD_TRACKS_LIMIT = 100


class SpotifyNotConfiguredError(Exception):
    """Raised when Spotify credentials are not configured."""

    def __init__(self) -> None:
        """Initialize with helpful message."""
        missing = [var for var in SPOTIFY_ENV_VARS if not os.environ.get(var)]
        msg = (
            "Spotify API credentials not configured. "
            f"Missing environment variables: {', '.join(missing)}"
        )
        super().__init__(msg)


class SpotifyClient:
    """Client for Spotify API operations."""

    def __init__(self) -> None:
        """Initialize the Spotify client.

        The client is lazy-initialized on first API call.
        """
        self._client: spotipy.Spotify | None = None

    @property
    def is_configured(self) -> bool:
        """Check if Spotify credentials are configured.

        Returns:
            True if all required environment variables are set.
        """
        return all(os.environ.get(var) for var in SPOTIFY_ENV_VARS)

    def _get_client(self) -> spotipy.Spotify:
        """Get or create the authenticated Spotify client.

        Returns:
            Authenticated spotipy client.

        Raises:
            SpotifyNotConfiguredError: If credentials are not configured.
        """
        if not self.is_configured:
            raise SpotifyNotConfiguredError()

        if self._client is None:
            auth_manager = SpotifyOAuth(
                scope="playlist-modify-public playlist-modify-private"
            )
            self._client = spotipy.Spotify(auth_manager=auth_manager)

        return self._client

    def _parse_track(self, track_data: dict[str, Any]) -> SpotifyTrack:
        """Parse Spotify API track data into SpotifyTrack.

        Args:
            track_data: Raw track data from Spotify API.

        Returns:
            Parsed SpotifyTrack.
        """
        artists = track_data.get("artists", [])
        artist_name = artists[0]["name"] if artists else ""

        return SpotifyTrack(
            id=track_data["id"],
            uri=track_data["uri"],
            title=track_data["name"],
            artist=artist_name,
            album=track_data.get("album", {}).get("name", ""),
            duration_ms=track_data.get("duration_ms", 0),
        )

    def search_track(
        self,
        title: str,
        artist: str,
        album: str | None = None,
    ) -> SpotifyTrack | None:
        """Search for a track with exact matching.

        Builds query: track:"title" artist:"artist" album:"album"

        Args:
            title: Track title.
            artist: Artist name.
            album: Album name (optional).

        Returns:
            SpotifyTrack if found, None otherwise.

        Raises:
            SpotifyNotConfiguredError: If credentials are not configured.
        """
        client = self._get_client()

        # Build query with exact matching
        query_parts = [f'track:"{title}"', f'artist:"{artist}"']
        if album:
            query_parts.append(f'album:"{album}"')
        query = " ".join(query_parts)

        results = client.search(q=query, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])

        if not tracks:
            return None

        return self._parse_track(tracks[0])

    def search_track_loose(
        self,
        title: str,
        artist: str,
    ) -> SpotifyTrack | None:
        """Search for a track without album filter.

        Builds query: track:"title" artist:"artist"

        Args:
            title: Track title.
            artist: Artist name.

        Returns:
            SpotifyTrack if found, None otherwise.

        Raises:
            SpotifyNotConfiguredError: If credentials are not configured.
        """
        return self.search_track(title=title, artist=artist, album=None)

    def create_playlist(
        self,
        name: str,
        description: str = "",
        public: bool = True,
    ) -> str:
        """Create a new Spotify playlist.

        Args:
            name: Playlist name.
            description: Playlist description.
            public: Whether the playlist is public.

        Returns:
            Playlist ID.

        Raises:
            SpotifyNotConfiguredError: If credentials are not configured.
        """
        client = self._get_client()
        user_id = client.current_user()["id"]

        result = client.user_playlist_create(
            user=user_id,
            name=name,
            public=public,
            description=description,
        )

        playlist_id: str = result["id"]
        return playlist_id

    def add_tracks(self, playlist_id: str, track_uris: list[str]) -> int:
        """Add tracks to a playlist with batching.

        Handles Spotify's 100 track limit per request by batching.

        Args:
            playlist_id: Playlist ID.
            track_uris: List of Spotify track URIs.

        Returns:
            Number of tracks added.

        Raises:
            SpotifyNotConfiguredError: If credentials are not configured.
        """
        if not track_uris:
            return 0

        client = self._get_client()
        total_added = 0

        # Batch tracks in groups of 100
        for i in range(0, len(track_uris), SPOTIFY_ADD_TRACKS_LIMIT):
            batch = track_uris[i : i + SPOTIFY_ADD_TRACKS_LIMIT]
            client.playlist_add_items(playlist_id, batch)
            total_added += len(batch)

        return total_added

    def get_playlist_url(self, playlist_id: str) -> str:
        """Get the URL for a playlist.

        Args:
            playlist_id: Playlist ID.

        Returns:
            Spotify playlist URL.
        """
        return f"https://open.spotify.com/playlist/{playlist_id}"
