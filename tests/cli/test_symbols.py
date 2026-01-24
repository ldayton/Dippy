"""Test cases for symbols (macOS symbol information tool)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (display info)
    ("symbols -help", True),
    ("symbols -v", True),
    ("symbols /usr/bin/ls", True),
    ("symbols -uuid /usr/bin/ls", True),
    ("symbols -arch x86_64 /usr/bin/ls", True),
    ("symbols -noHeaders /usr/bin/ls", True),
    ("symbols -lookup 0x1234 /usr/bin/ls", True),
    ("symbols -lookup main /usr/bin/ls", True),
    ("symbols -printSignature /usr/bin/ls", True),
    ("symbols -w /usr/bin/ls", True),
    # Save signature to file - needs confirmation (redirect target)
    ("symbols -saveSignature /tmp/sig.txt /usr/bin/ls", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_symbols(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


def test_symbols_save_has_redirect_target():
    """Verify -saveSignature flag returns redirect_targets for config rule checking."""
    from dippy.cli import HandlerContext
    from dippy.cli.symbols import classify

    result = classify(
        HandlerContext(["symbols", "-saveSignature", "/tmp/sig.txt", "/usr/bin/ls"])
    )
    assert "/tmp/sig.txt" in result.redirect_targets
