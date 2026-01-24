"""Test cases for compression_tool (macOS compression utility)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (help, stdout output)
    ("compression_tool -h", True),
    ("compression_tool -encode -i input.dat", True),  # stdout
    ("compression_tool -decode -i input.lzfse", True),  # stdout
    ("compression_tool -encode -a lz4 -i input.dat", True),  # stdout
    ("compression_tool -decode -a zlib -i input.z", True),  # stdout
    # Output to file - needs confirmation (redirect target)
    ("compression_tool -encode -i input.dat -o output.lzfse", False),
    ("compression_tool -decode -i input.lzfse -o output.dat", False),
    ("compression_tool -encode -a lzma -i input.dat -o output.xz", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_compression_tool(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


def test_compression_tool_output_has_redirect_target():
    """Verify -o flag returns redirect_targets for config rule checking."""
    from dippy.cli import HandlerContext
    from dippy.cli.compression_tool import classify

    result = classify(
        HandlerContext(
            ["compression_tool", "-encode", "-i", "input.dat", "-o", "output.lzfse"]
        )
    )
    assert "output.lzfse" in result.redirect_targets
