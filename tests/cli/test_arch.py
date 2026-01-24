"""Test cases for arch."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # No arguments - prints architecture
    ("arch", True),
    # Delegate to inner command - safe inner
    ("arch -x86_64 ls", True),
    ("arch -arm64 cat foo.txt", True),
    ("arch --arch x86_64 pwd", True),
    # Delegate to inner command - unsafe inner
    ("arch -x86_64 rm foo", False),
    ("arch -arm64 rm -rf /", False),
    # Multiple arch flags
    ("arch -x86_64 -arm64 ls", True),
    # Other flags before command
    ("arch -32 ls", True),
    ("arch -64 ls", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
