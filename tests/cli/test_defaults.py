"""Test cases for defaults."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("defaults read", True),
    ("defaults read com.apple.Finder", True),
    ("defaults read com.apple.Finder ShowPathbar", True),
    ("defaults read -app Safari", True),
    ("defaults read-type com.apple.Finder ShowPathbar", True),
    ("defaults domains", True),
    ("defaults find keyword", True),
    ("defaults help", True),
    # Global flags with read
    ("defaults -currentHost read", True),
    ("defaults -host localhost read com.apple.Finder", True),
    # Write operations - unsafe
    ("defaults write com.apple.Finder ShowPathbar -bool true", False),
    ("defaults write com.apple.Dock expose-animation-duration -float 0.1", False),
    # Rename - unsafe
    ("defaults rename com.apple.Finder old_key new_key", False),
    # Delete - unsafe
    ("defaults delete com.apple.Finder", False),
    ("defaults delete com.apple.Finder ShowPathbar", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
