"""
Tests for base64 command (encoding/decoding utility).

base64 is a data transformation utility that reads input and outputs
base64-encoded/decoded data. It's always safe as a SIMPLE_SAFE command
since it only transforms data (output redirects are handled separately).
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Basic encoding (default) ===
    ("base64 file.txt", True),
    ("base64", True),  # reads from stdin
    #
    # === SAFE: Explicit encode flag ===
    ("base64 -e file.txt", True),
    ("base64 --encode file.txt", True),
    #
    # === SAFE: Decode flag ===
    ("base64 -d file.txt", True),
    ("base64 --decode file.txt", True),
    ("base64 -d", True),  # decode from stdin
    #
    # === SAFE: Wrap flag (output formatting) ===
    ("base64 -w 0 file.txt", True),
    ("base64 --wrap 76 file.txt", True),
    ("base64 -w 0", True),
    #
    # === SAFE: Error checking flag ===
    ("base64 -n file.txt", True),
    ("base64 --noerrcheck file.txt", True),
    ("base64 -d -n file.txt", True),
    #
    # === SAFE: Help and version ===
    ("base64 --help", True),
    ("base64 -u", True),  # -u is help in some versions
    ("base64 --version", True),
    ("base64 --copyright", True),
    #
    # === SAFE: Combined flags ===
    ("base64 -d -w 0 file.txt", True),
    ("base64 --decode --wrap 0 file.txt", True),
    #
    # === SAFE: Pipeline usage ===
    ("echo 'hello' | base64", True),
    ("base64 -d | cat", True),
    ("cat file.txt | base64 | base64 -d", True),
    #
    # === UNSAFE: Output redirect (handled by has_output_redirect) ===
    ("base64 file.txt > output.txt", False),
    ("base64 -d file.txt > decoded.bin", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that base64 command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
