"""Test cases for sysctl."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("sysctl -a", True),
    ("sysctl kern.maxfiles", True),
    ("sysctl -n hw.model", True),
    ("sysctl -n machdep.cpu.brand_string", True),
    ("sysctl hw.memsize hw.ncpu", True),
    ("sysctl -e kern.hostname", True),
    ("sysctl -d kern.maxfiles", True),
    # Write operations - unsafe
    ("sysctl kern.maxfiles=12345", False),
    ("sysctl -w kern.maxfiles=12345", False),
    ("sysctl kern.maxfiles=12345,67890", False),
    ("sysctl -f /etc/sysctl.conf", False),
    # Multiple with one write
    ("sysctl kern.hostname kern.maxfiles=100", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
