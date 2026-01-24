"""Test cases for lipo (macOS universal binary tool)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (info/verify)
    ("lipo -info binary", True),
    ("lipo -archs binary", True),
    ("lipo -detailed_info binary", True),
    ("lipo binary -verify_arch x86_64 arm64", True),
    ("lipo -info fat.o", True),
    # Unsafe operations (write to output) - need confirmation (redirect target)
    ("lipo -create x86.o arm64.o -output universal.o", False),
    ("lipo -extract x86_64 universal.o -output x86.o", False),
    ("lipo -extract_family arm64 universal.o -output arm.o", False),
    ("lipo -remove x86_64 universal.o -output arm_only.o", False),
    ("lipo -replace x86_64 new_x86.o universal.o -output updated.o", False),
    ("lipo -thin arm64 universal.o -output thin.o", False),
    # Write command without -output should ask
    ("lipo -create x86.o arm64.o", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_lipo(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


def test_lipo_output_has_redirect_target():
    """Verify -output flag returns redirect_targets for config rule checking."""
    from dippy.cli import HandlerContext
    from dippy.cli.lipo import classify

    result = classify(
        HandlerContext(
            ["lipo", "-create", "x86.o", "arm64.o", "-output", "universal.o"]
        )
    )
    assert "universal.o" in result.redirect_targets
