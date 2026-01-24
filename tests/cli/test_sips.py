"""Test cases for sips (macOS scriptable image processing)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (query)
    ("sips -g pixelWidth image.png", True),
    ("sips --getProperty pixelHeight image.png", True),
    ("sips -g all image.png", True),
    ("sips --verify profile.icc", True),
    ("sips -g format image.png", True),
    ("sips image.png", True),  # Just querying file
    # Unsafe operations (modify in place) - need confirmation
    ("sips -s format jpeg image.png", False),
    ("sips --setProperty format png image.jpg", False),
    ("sips -r 90 image.png", False),
    ("sips --rotate 180 image.png", False),
    ("sips -f horizontal image.png", False),
    ("sips --flip vertical image.png", False),
    ("sips -z 100 100 image.png", False),
    ("sips --resampleHeightWidth 200 200 image.png", False),
    ("sips -Z 500 image.png", False),
    ("sips -c 100 100 image.png", False),
    ("sips -p 200 200 image.png", False),
    ("sips -i image.png", False),
    ("sips --addIcon image.png", False),
    ("sips -d dpiWidth image.png", False),
    ("sips --deleteProperty dpiHeight image.png", False),
    ("sips -e profile.icc image.png", False),
    ("sips --embedProfile profile.icc image.png", False),
    # Output to different file - needs confirmation (redirect target)
    ("sips -s format jpeg -o output.jpg image.png", False),
    ("sips --out output.png -z 100 100 image.png", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_sips(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


def test_sips_output_has_redirect_target():
    """Verify -o flag returns redirect_targets for config rule checking."""
    from dippy.cli import HandlerContext
    from dippy.cli.sips import classify

    result = classify(
        HandlerContext(
            ["sips", "-s", "format", "jpeg", "-o", "output.jpg", "image.png"]
        )
    )
    assert "output.jpg" in result.redirect_targets
