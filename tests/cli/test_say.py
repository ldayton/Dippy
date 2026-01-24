"""Test cases for say (macOS text-to-speech)."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations (speaks to audio output)
    ("say hello", True),
    ("say 'Hello, world!'", True),
    ("say -v Alex hello", True),
    ("say -r 200 hello", True),
    ("say -f input.txt", True),
    ("say --voice=Samantha hello", True),
    ("say --rate=150 hello", True),
    # Output to file needs confirmation (redirect target, no allow-redirect rule)
    ("say -o output.aiff hello", False),
    ("say --output-file output.aiff hello", False),
    ("say --output-file=output.aiff hello", False),
    ("say -v Alex -o speech.aiff hello", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_say(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


def test_say_output_has_redirect_target():
    """Verify -o flag returns redirect_targets for config rule checking."""
    from dippy.cli import HandlerContext
    from dippy.cli.say import classify

    result = classify(HandlerContext(["say", "-o", "output.aiff", "hello"]))
    assert "output.aiff" in result.redirect_targets
