"""
Tests for sleep command.

Sleep is always safe - it only delays execution and has no destructive flags.
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Basic delay commands ===
    ("sleep 1", True),
    ("sleep 5", True),
    ("sleep 10", True),
    ("sleep 0.5", True),  # fractional seconds
    ("sleep .5", True),  # leading dot
    ("sleep 1.5", True),
    #
    # === SAFE: With suffixes ===
    ("sleep 1s", True),  # seconds
    ("sleep 2m", True),  # minutes
    ("sleep 1h", True),  # hours
    ("sleep 1d", True),  # days
    #
    # === SAFE: Multiple arguments (summed) ===
    ("sleep 1 2", True),
    ("sleep 1s 2s", True),
    ("sleep 1m 30s", True),
    #
    # === SAFE: Help and version ===
    ("sleep --help", True),
    ("sleep --version", True),
    #
    # === SAFE: Used in command chains ===
    ("sleep 1 && echo done", True),
    ("sleep 2 && ls", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
