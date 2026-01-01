"""Song matching engine for KUTX to Spotify integration."""

from kutx2spotify.cache import Resolution, ResolutionCache
from kutx2spotify.models import Match, MatchResult, MatchStatus, Song, SpotifyTrack
from kutx2spotify.spotify import SpotifyClient

# Duration tolerance in milliseconds (10 seconds)
DURATION_TOLERANCE_MS = 10_000


class Matcher:
    """Matches KUTX songs to Spotify tracks.

    Matching algorithm:
    1. Check resolution cache first (user-stored decisions)
    2. Exact match: search with album, verify album matches
    3. Album fallback: search without album if exact not found
    4. Duration filter: prefer tracks within +/- 10 seconds
    5. Popularity tiebreaker: pick most popular if multiple matches
    """

    def __init__(
        self,
        spotify_client: SpotifyClient,
        resolution_cache: ResolutionCache | None = None,
    ) -> None:
        """Initialize the matcher.

        Args:
            spotify_client: Client for Spotify API operations.
            resolution_cache: Optional cache for stored match resolutions.
        """
        self._spotify = spotify_client
        self._cache = resolution_cache

    def _albums_match(self, kutx_album: str, spotify_album: str) -> bool:
        """Check if albums match (case-insensitive).

        Args:
            kutx_album: Album name from KUTX.
            spotify_album: Album name from Spotify.

        Returns:
            True if albums match.
        """
        return kutx_album.lower() == spotify_album.lower()

    def _is_within_duration_tolerance(self, song: Song, track: SpotifyTrack) -> bool:
        """Check if track duration is within tolerance of song duration.

        Args:
            song: The KUTX song.
            track: The Spotify track.

        Returns:
            True if duration difference is within tolerance.
        """
        diff = abs(song.duration_ms - track.duration_ms)
        return diff <= DURATION_TOLERANCE_MS

    def _find_exact_match(self, song: Song) -> SpotifyTrack | None:
        """Try to find an exact match (with album).

        Args:
            song: The KUTX song to match.

        Returns:
            SpotifyTrack if exact match found, None otherwise.
        """
        track = self._spotify.search_track(
            title=song.title,
            artist=song.artist,
            album=song.album,
        )

        if track is None:
            return None

        # Verify album actually matches
        if not self._albums_match(song.album, track.album):
            return None

        return track

    def _find_best_fallback(self, song: Song) -> tuple[SpotifyTrack | None, bool]:
        """Find best fallback match without album constraint.

        Searches for tracks and applies duration filter and popularity sort.

        Args:
            song: The KUTX song to match.

        Returns:
            Tuple of (best track or None, within_tolerance bool).
            within_tolerance is True if track is within duration tolerance.
        """
        tracks = self._spotify.search_tracks(
            title=song.title,
            artist=song.artist,
        )

        if not tracks:
            return None, False

        # Separate tracks into within-tolerance and outside-tolerance
        within_tolerance = [
            t for t in tracks if self._is_within_duration_tolerance(song, t)
        ]
        outside_tolerance = [
            t for t in tracks if not self._is_within_duration_tolerance(song, t)
        ]

        # Prefer tracks within tolerance, sorted by popularity
        if within_tolerance:
            best = max(within_tolerance, key=lambda t: t.popularity)
            return best, True

        # Fall back to outside tolerance, sorted by popularity
        if outside_tolerance:
            best = max(outside_tolerance, key=lambda t: t.popularity)
            return best, False

        return None, False

    def _check_resolution_cache(self, song: Song) -> Match | None:
        """Check if song has a cached resolution.

        Args:
            song: The KUTX song to check.

        Returns:
            Match if cached resolution found, None otherwise.
        """
        if self._cache is None:
            return None

        resolution = self._cache.get(song)
        if resolution is None:
            return None

        # Create a SpotifyTrack from the resolution
        # Note: We only have URI and album from resolution
        track = SpotifyTrack(
            id=resolution.spotify_uri.split(":")[-1],
            uri=resolution.spotify_uri,
            title=song.title,
            artist=song.artist,
            album=resolution.resolved_album,
            duration_ms=song.duration_ms,  # Use song's duration as placeholder
            popularity=100,  # User-resolved, treat as high priority
        )

        # Determine status based on album match
        if self._albums_match(song.album, resolution.resolved_album):
            status = MatchStatus.EXACT
        else:
            status = MatchStatus.ALBUM_FALLBACK

        return Match(song=song, track=track, status=status)

    def match_song(self, song: Song) -> Match:
        """Match a single song to a Spotify track.

        Implements the matching algorithm:
        1. Check resolution cache
        2. Try exact match (with album)
        3. Try album fallback (without album)
        4. Apply duration filter and popularity sort

        Args:
            song: The KUTX song to match.

        Returns:
            Match result with track and status.
        """
        # Step 1: Check resolution cache
        cached = self._check_resolution_cache(song)
        if cached is not None:
            return cached

        # Step 2: Try exact match
        exact_track = self._find_exact_match(song)
        if exact_track is not None:
            # Check duration for exact match
            if self._is_within_duration_tolerance(song, exact_track):
                return Match(song=song, track=exact_track, status=MatchStatus.EXACT)
            else:
                return Match(
                    song=song, track=exact_track, status=MatchStatus.DURATION_MISMATCH
                )

        # Step 3: Try album fallback
        fallback_track, within_tolerance = self._find_best_fallback(song)
        if fallback_track is None:
            return Match(song=song, track=None, status=MatchStatus.NOT_FOUND)

        # Check if album matches (could be exact after all)
        if self._albums_match(song.album, fallback_track.album):
            if within_tolerance:
                return Match(
                    song=song, track=fallback_track, status=MatchStatus.EXACT
                )
            else:
                return Match(
                    song=song,
                    track=fallback_track,
                    status=MatchStatus.DURATION_MISMATCH,
                )

        # Album doesn't match - it's a fallback
        if within_tolerance:
            return Match(
                song=song, track=fallback_track, status=MatchStatus.ALBUM_FALLBACK
            )
        else:
            return Match(
                song=song, track=fallback_track, status=MatchStatus.DURATION_MISMATCH
            )

    def match_songs(self, songs: list[Song]) -> MatchResult:
        """Match multiple songs to Spotify tracks.

        Gracefully handles when Spotify is not configured by returning
        NOT_FOUND for all songs.

        Args:
            songs: List of KUTX songs to match.

        Returns:
            MatchResult containing all matches.
        """
        result = MatchResult()

        # Check if Spotify is configured
        if not self._spotify.is_configured:
            for song in songs:
                result.add(Match(song=song, track=None, status=MatchStatus.NOT_FOUND))
            return result

        # Match each song
        for song in songs:
            match = self.match_song(song)
            result.add(match)

        return result
