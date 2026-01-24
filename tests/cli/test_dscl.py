"""Test cases for dscl."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("dscl . -read /Users/alice", True),
    ("dscl . -readall /Users", True),
    ("dscl . -list /Users", True),
    ("dscl . -search /Users name alice", True),
    ("dscl . -diff /Users/alice /Users/bob", True),
    # Without leading dash
    ("dscl . read /Users/alice", True),
    ("dscl . list /Users", True),
    # With options before datasource
    ("dscl -plist . -read /Users/alice", True),
    ("dscl -raw . -list /Users", True),
    # Write operations - unsafe
    ("dscl . -create /Users/newuser", False),
    ("dscl . -append /Users/alice name bob", False),
    ("dscl . -merge /Users/alice name bob", False),
    ("dscl . -delete /Users/alice", False),
    ("dscl . -change /Users/alice name old new", False),
    ("dscl . -passwd /Users/alice", False),
    # Without leading dash
    ("dscl . create /Users/newuser", False),
    ("dscl . delete /Users/alice", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
