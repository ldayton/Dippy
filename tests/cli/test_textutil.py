"""Test cases for textutil (macOS text file conversion)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (info/help)
    ("textutil -info foo.rtf", True),
    ("textutil -help", True),
    ("textutil --help", True),
    # Safe with -stdout (no file written)
    ("textutil -convert txt -stdout foo.rtf", True),
    ("textutil -cat html -stdout foo.rtf bar.rtf", True),
    # Unsafe operations (write files) - need confirmation
    ("textutil -convert html foo.rtf", False),
    ("textutil -convert rtf -font Times foo.txt", False),
    ("textutil -cat html -title 'Combined' foo.rtf bar.rtf", False),
    ("textutil -convert txt -output out.txt foo.rtf", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_textutil(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


def test_textutil_output_has_redirect_target():
    """Verify -output flag returns redirect_targets for config rule checking."""
    from dippy.cli import HandlerContext
    from dippy.cli.textutil import classify

    result = classify(
        HandlerContext(["textutil", "-convert", "txt", "-output", "out.txt", "foo.rtf"])
    )
    assert "out.txt" in result.redirect_targets
