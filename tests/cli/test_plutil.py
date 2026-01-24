"""Test cases for plutil (macOS property list utility)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (read/lint)
    ("plutil -p file.plist", True),
    ("plutil -lint file.plist", True),
    ("plutil -extract key json file.plist", True),
    ("plutil file.plist", True),
    # Unsafe operations (modify) - need confirmation (redirect targets, no allow rule)
    ("plutil -convert xml1 file.plist", False),
    ("plutil -convert json -o out.json file.plist", False),
    ("plutil -insert key -string value file.plist", False),
    ("plutil -replace key -string newvalue file.plist", False),
    ("plutil -remove key file.plist", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_plutil(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


def test_plutil_convert_inplace_has_redirect_target():
    """Verify -convert without -o returns input file as redirect_target."""
    from dippy.cli import HandlerContext
    from dippy.cli.plutil import classify

    result = classify(HandlerContext(["plutil", "-convert", "xml1", "file.plist"]))
    assert "file.plist" in result.redirect_targets


def test_plutil_convert_output_has_redirect_target():
    """Verify -convert with -o returns output file as redirect_target."""
    from dippy.cli import HandlerContext
    from dippy.cli.plutil import classify

    result = classify(
        HandlerContext(["plutil", "-convert", "json", "-o", "out.json", "file.plist"])
    )
    assert "out.json" in result.redirect_targets


def test_plutil_insert_has_redirect_target():
    """Verify -insert returns input file as redirect_target."""
    from dippy.cli import HandlerContext
    from dippy.cli.plutil import classify

    result = classify(
        HandlerContext(["plutil", "-insert", "key", "-string", "value", "file.plist"])
    )
    assert "file.plist" in result.redirect_targets
