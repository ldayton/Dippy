"""Test cases for codesign (macOS code signing)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (display/verify)
    ("codesign -d /path/to/app", True),
    ("codesign --display /path/to/app", True),
    ("codesign -v /path/to/app", True),
    ("codesign --verify /path/to/app", True),
    ("codesign -dv /path/to/app", True),
    ("codesign -dvv /path/to/app", True),
    ("codesign -h 1234", True),
    ("codesign --validate-constraint /path/to/app", True),
    ("codesign -d --entitlements - /path/to/app", True),
    ("codesign -v --deep /path/to/app", True),
    # Unsafe operations (signing)
    ("codesign -s 'Developer ID' /path/to/app", False),
    ("codesign --sign 'Developer ID' /path/to/app", False),
    ("codesign -s - /path/to/app", False),
    ("codesign -fs 'Developer ID' /path/to/app", False),
    ("codesign --remove-signature /path/to/app", False),
    ("codesign -s 'Developer ID' --deep /path/to/app", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_codesign(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
