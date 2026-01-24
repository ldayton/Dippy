"""Test cases for spctl."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Read operations - safe
    ("spctl --assess /Applications/Safari.app", True),
    ("spctl -a /Applications/Safari.app", True),
    ("spctl --assess -t execute /usr/bin/ls", True),
    ("spctl --assess --verbose /Applications/Safari.app", True),
    ("spctl --status", True),
    ("spctl --disable-status", True),
    # Write operations - unsafe
    ("spctl --global-enable", False),
    ("spctl --global-disable", False),
    ("spctl --master-enable", False),
    ("spctl --master-disable", False),
    ("spctl --add /Applications/MyApp.app", False),
    ("spctl --add --label MyRule /Applications/MyApp.app", False),
    ("spctl --disable --label MyRule", False),
    ("spctl --enable --label MyRule", False),
    ("spctl --remove --label MyRule", False),
    ("spctl --reset-default", False),
    # No arguments - unsafe (interactive)
    ("spctl", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
