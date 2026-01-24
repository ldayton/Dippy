"""Test cases for binhex/applesingle/macbinary (macOS file encoding)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (help, version, probe, pipe)
    ("binhex -h", True),
    ("binhex --help", True),
    ("binhex -V", True),
    ("binhex --version", True),
    ("binhex probe file.hqx", True),
    ("applesingle probe file.as", True),
    ("macbinary probe file.bin", True),
    # Pipe mode (stdout) is safe
    ("binhex decode -c file.hqx", True),
    ("binhex encode -c file.txt", True),
    ("applesingle decode --pipe file.as", True),
    ("macbinary decode --to-stdout file.bin", True),
    # Encode/decode without pipe writes files - needs confirmation
    ("binhex encode file.txt", False),
    ("binhex decode file.hqx", False),
    ("applesingle encode file.txt", False),
    ("macbinary encode file.txt", False),
    # With output file - needs confirmation (redirect target)
    ("binhex encode -o output.hqx file.txt", False),
    ("binhex decode -o output.txt file.hqx", False),
    # With output directory - needs confirmation
    ("binhex decode -C /tmp file.hqx", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_binhex(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


def test_binhex_output_has_redirect_target():
    """Verify -o flag returns redirect_targets for config rule checking."""
    from dippy.cli import HandlerContext
    from dippy.cli.binhex import classify

    result = classify(
        HandlerContext(["binhex", "encode", "-o", "output.hqx", "file.txt"])
    )
    assert "output.hqx" in result.redirect_targets
