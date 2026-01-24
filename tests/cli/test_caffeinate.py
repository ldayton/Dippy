"""Test cases for caffeinate."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # No utility - just prevents sleep
    ("caffeinate", True),
    ("caffeinate -d", True),
    ("caffeinate -i", True),
    ("caffeinate -m", True),
    ("caffeinate -s", True),
    ("caffeinate -u", True),
    ("caffeinate -disu", True),
    ("caffeinate -t 3600", True),
    ("caffeinate -w 1234", True),
    ("caffeinate -u -t 3600", True),
    # Delegate to inner command - safe inner
    ("caffeinate -i ls -la", True),
    ("caffeinate ls", True),
    # Delegate to inner command - unsafe inner
    ("caffeinate -i rm -rf /", False),
    ("caffeinate rm foo", False),
    ("caffeinate -i make", False),  # make not in SIMPLE_SAFE
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
