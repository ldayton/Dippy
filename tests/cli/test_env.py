"""
Comprehensive tests for env CLI handler.

Env runs commands with modified environment - we check the inner command.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Just viewing environment ===
    ("env", True),  # prints environment
    ("env -0", True),  # null-separated
    ("env --null", True),
    #
    # === SAFE: Running safe inner commands ===
    ("env ls", True),
    ("env pwd", True),
    ("env cat /etc/passwd", True),
    ("env FOO=bar ls", True),
    ("env FOO=bar BAZ=qux ls", True),
    ("env -u PATH ls", True),  # unset with safe command
    ("env --unset PATH ls", True),
    ("env -i ls", True),  # empty env with safe command
    ("env --ignore-environment ls", True),
    ("env - ls", True),  # same as -i
    ("env -C /tmp ls", True),
    ("env --chdir=/tmp ls", True),
    ("env FOO=bar -- ls", True),  # -- separator
    #
    # === UNSAFE: Running unsafe inner commands ===
    ("env rm file.txt", False),
    ("env FOO=bar rm file.txt", False),
    ("env -i rm -rf /", False),
    ("env -- rm file.txt", False),
    ("env mv src dst", False),
    ("env python script.py", False),  # unknown command
    ("env npm install", False),
    ("env sudo ls", False),
    ("env FOO=bar BAZ=qux rm file.txt", False),
    #
    # === EDGE CASES ===
    ("env FOO=bar", True),  # just setting env, no command
    ("env -S 'FOO=bar ls'", True),  # split string with safe command
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
