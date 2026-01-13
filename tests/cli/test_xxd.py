"""Test cases for xxd."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (hex dump)
    ("xxd file.bin", True),
    ("xxd -l 120 file.bin", True),
    ("xxd -c 12 file.bin", True),
    ("xxd -b file.bin", True),
    ("xxd -i file.bin", True),
    ("xxd -p file.bin", True),
    ("xxd -u file.bin", True),
    ("xxd -a file.bin", True),
    ("xxd -s 0x30 file.bin", True),
    ("xxd -e file.bin", True),
    ("xxd --help", True),
    ("xxd -v", True),
    ("xxd --version", True),
    # Unsafe operations (revert mode writes files)
    ("xxd -r file.hex", False),
    ("xxd -revert file.hex", False),
    ("xxd -r -p file.hex", False),
    ("xxd -r -s 100 file.hex output.bin", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_xxd(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
