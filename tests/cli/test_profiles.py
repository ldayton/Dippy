"""Test cases for profiles."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("profiles help", True),
    ("profiles status", True),
    ("profiles status -type configuration", True),
    ("profiles list", True),
    ("profiles list -verbose", True),
    ("profiles list -type provisioning", True),
    ("profiles list -user alice", True),
    ("profiles show", True),
    ("profiles show -type configuration", True),
    ("profiles show -all", True),
    ("profiles validate -path /path/to/profile.mobileconfig", True),
    ("profiles validate -type enrollment", True),
    ("profiles version", True),
    # Write operations - unsafe
    ("profiles remove -identifier com.example.profile", False),
    ("profiles remove -all", False),
    ("profiles remove -forced -identifier com.example.profile", False),
    ("profiles sync", False),
    ("profiles sync -type configuration", False),
    ("profiles renew -identifier com.example.profile", False),
    ("profiles renew -type configuration", False),
    # No arguments - unsafe
    ("profiles", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
