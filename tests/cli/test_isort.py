"""Tests for isort CLI handler."""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Read-only modes ===
    ("isort --check-only", True),
    ("isort --check-only .", True),
    ("isort --check", True),
    ("isort -c", True),
    ("isort -c src/", True),
    ("isort --diff", True),
    ("isort -d", True),
    ("isort --diff file.py", True),
    ("isort --check-only --diff", True),
    #
    # === UNSAFE: Sorting (modifies code) ===
    ("isort", False),
    ("isort .", False),
    ("isort src/", False),
    ("isort file.py", False),
    ("isort --profile black .", False),
    ("isort --line-length 100 .", False),
    ("isort --atomic .", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
