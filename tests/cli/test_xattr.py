"""Test cases for xattr (macOS extended attributes)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (read/list attributes)
    ("xattr file.txt", True),
    ("xattr -l file.txt", True),
    ("xattr -p com.apple.quarantine file.txt", True),
    ("xattr -pl com.apple.quarantine file.txt", True),
    ("xattr -lx file.txt", True),
    ("xattr -px com.apple.metadata file.txt", True),
    # Unsafe operations (modify attributes)
    ("xattr -w com.apple.quarantine 0 file.txt", False),
    ("xattr -d com.apple.quarantine file.txt", False),
    ("xattr -c file.txt", False),
    # Combined flags with unsafe operations
    ("xattr -wd com.apple.quarantine file.txt", False),
    ("xattr -cd file.txt", False),
    ("xattr -cr /path/to/dir", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_xattr(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
