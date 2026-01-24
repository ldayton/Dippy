"""Test cases for mdimport."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Test mode - doesn't store in Spotlight index
    ("mdimport -t file.txt", True),
    ("mdimport -t -d1 file.txt", True),
    ("mdimport -t -d2 file.txt", True),
    ("mdimport -t -d3 file.txt", True),
    # List plugins/schema
    ("mdimport -L", True),
    ("mdimport -A", True),
    ("mdimport -X", True),
    # Actually imports to Spotlight
    ("mdimport file.txt", False),
    ("mdimport -i file.txt", False),
    ("mdimport -r plugin.mdimporter", False),
    ("mdimport /path/to/directory", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
