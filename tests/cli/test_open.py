"""Test cases for open."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Reveal in Finder - safe
    ("open -R file.txt", True),
    ("open -R /path/to/file", True),
    ("open -R .", True),
    # Opening files/directories - launches apps
    ("open file.txt", False),
    ("open .", False),
    ("open /Applications", False),
    # Opening URLs - external effect
    ("open https://example.com", False),
    ("open http://example.com", False),
    # Opening with specific app
    ("open -a Safari", False),
    ("open -a TextEdit file.txt", False),
    ("open -b com.apple.Safari", False),
    # Other flags
    ("open -e file.txt", False),  # Open with TextEdit
    ("open -t file.txt", False),  # Open with default text editor
    ("open -n -a Safari", False),  # New instance
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
