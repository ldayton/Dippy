"""Test cases for scutil."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("scutil --get ComputerName", True),
    ("scutil --get HostName", True),
    ("scutil --get LocalHostName", True),
    ("scutil --dns", True),
    ("scutil --proxy", True),
    ("scutil -r example.com", True),
    ("scutil -r 192.168.1.1", True),
    ("scutil -r -W example.com", True),
    ("scutil -w State:/Network/Global/IPv4", True),
    ("scutil -w State:/Network/Global/IPv4 -t 10", True),
    # Write operations - unsafe
    ("scutil --set ComputerName MyMac", False),
    ("scutil --set HostName myhost.local", False),
    ("scutil --set LocalHostName mylocal", False),
    ("scutil --renew en0", False),
    # Interactive/VPN modes - unsafe
    ("scutil", False),
    ("scutil --prefs", False),
    ("scutil --nc list", False),
    ("scutil --nc start MyVPN", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
