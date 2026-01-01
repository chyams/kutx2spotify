"""Basic tests for kutx2spotify."""

from kutx2spotify import __version__


def test_version() -> None:
    """Test version is set."""
    assert __version__ == "0.1.0"
