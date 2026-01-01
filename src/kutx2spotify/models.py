"""Data models for KUTX to Spotify integration."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MatchStatus(Enum):
    """Status of a Spotify track match."""

    EXACT = "exact"
    ALBUM_FALLBACK = "album_fallback"
    DURATION_MISMATCH = "duration_mismatch"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class Song:
    """A song from the KUTX playlist."""

    title: str
    artist: str
    album: str
    duration_ms: int
    played_at: datetime

    @property
    def duration_seconds(self) -> int:
        """Duration in seconds."""
        return self.duration_ms // 1000

    def duration_display(self) -> str:
        """Human-readable duration (MM:SS)."""
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes}:{seconds:02d}"


@dataclass(frozen=True)
class SpotifyTrack:
    """A track from Spotify."""

    id: str
    uri: str
    title: str
    artist: str
    album: str
    duration_ms: int


@dataclass(frozen=True)
class Match:
    """A match between a KUTX song and a Spotify track."""

    song: Song
    track: SpotifyTrack | None
    status: MatchStatus

    @property
    def has_issue(self) -> bool:
        """Whether this match has a potential issue."""
        return self.status in (
            MatchStatus.DURATION_MISMATCH,
            MatchStatus.NOT_FOUND,
        )


@dataclass
class MatchResult:
    """Aggregated results from matching songs to Spotify tracks."""

    matches: list[Match] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of matches."""
        return len(self.matches)

    @property
    def found(self) -> int:
        """Number of songs that found a Spotify match."""
        return sum(1 for m in self.matches if m.track is not None)

    @property
    def not_found(self) -> int:
        """Number of songs without a Spotify match."""
        return sum(1 for m in self.matches if m.track is None)

    @property
    def exact_matches(self) -> int:
        """Number of exact matches."""
        return sum(1 for m in self.matches if m.status == MatchStatus.EXACT)

    @property
    def issues(self) -> list[Match]:
        """Matches with potential issues."""
        return [m for m in self.matches if m.has_issue]

    def add(self, match: Match) -> None:
        """Add a match to the results."""
        self.matches.append(match)
