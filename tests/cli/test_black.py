"""Tests for black CLI handler."""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Read-only modes ===
    ("black --check", True),
    ("black --check .", True),
    ("black --check src/", True),
    ("black --diff", True),
    ("black --diff file.py", True),
    ("black --check --diff", True),
    #
    # === UNSAFE: Formatting (modifies code) ===
    ("black", False),
    ("black .", False),
    ("black src/", False),
    ("black file.py", False),
    ("black --line-length 100 .", False),
    ("black --target-version py39 .", False),
    ("black --fast .", False),
    ("black --quiet .", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
