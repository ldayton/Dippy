"""Test cases for mktemp."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Dry run - just prints name without creating
    ("mktemp -u", True),
    ("mktemp -u template.XXXX", True),
    ("mktemp -u -t prefix", True),
    # Actually creates files/directories
    ("mktemp", False),
    ("mktemp -d", False),
    ("mktemp template.XXXX", False),
    ("mktemp -t prefix", False),
    ("mktemp -p /tmp", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
