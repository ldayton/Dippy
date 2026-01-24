"""Test cases for qlmanage (macOS Quick Look management)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (display/info)
    ("qlmanage -m", True),
    ("qlmanage -t file.pdf", True),
    ("qlmanage -t -s 512 file.pdf", True),
    ("qlmanage -p file.pdf", True),
    ("qlmanage -p -x file.pdf", True),
    ("qlmanage -h", True),
    # Unsafe operations (reset server)
    ("qlmanage -r", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_qlmanage(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
