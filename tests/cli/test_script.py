"""Tests for script CLI handler."""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation
from dippy.core.config import Config, Rule


TESTS = [
    # === SAFE: Command delegation with safe inner commands ===
    ("script -q /dev/null ls", True),
    ("script -q /dev/null pwd", True),
    ("script -q /dev/null git status", True),
    ("script -q /dev/null echo hello", True),
    ("script /tmp/out.log ls -la", True),
    ("script -a /tmp/out.log cat file.txt", True),
    ("script -aq /dev/null ls", True),
    ("script -q -a /dev/null ls", True),
    #
    # === SAFE: Playback mode (just reading a file) ===
    ("script -p typescript", True),
    ("script -dp typescript", True),
    ("script -p -d typescript", True),
    #
    # === UNSAFE: Interactive sessions ===
    ("script", False),
    ("script typescript", False),
    ("script -a typescript", False),
    ("script -q /dev/null", False),
    #
    # === UNSAFE: Command delegation with unsafe inner commands ===
    ("script -q /dev/null rm file.txt", False),
    ("script -q /dev/null npm install", False),
    ("script /tmp/out.log python script.py", False),
    ("script -q /dev/null bash -c 'rm -rf /'", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"


class TestScriptConfigIntegration:
    """Test that script respects user config rules."""

    def test_config_allow_script_pattern_bypasses_handler(self, check):
        """Config rule for script pattern approves before handler runs."""
        config = Config(rules=[Rule("allow", "script -q /dev/null")])
        # This would normally be blocked (rm is unsafe), but config takes priority
        result = check("script -q /dev/null rm -rf /", config=config)
        assert is_approved(result)

    def test_config_deny_inner_command_blocks(self, check):
        """Config deny rule on inner command blocks delegation."""
        config = Config(rules=[Rule("deny", "rm", message="use trash")])
        result = check("script -q /dev/null rm foo.txt", config=config)
        assert not is_approved(result)

    def test_config_allow_inner_command_approves(self, check):
        """Config allow rule on inner command approves delegation."""
        config = Config(rules=[Rule("allow", "python")])
        # python script.py normally needs confirmation, but config allows it
        result = check("script -q /dev/null python script.py", config=config)
        assert is_approved(result)

    def test_config_deny_script_blocks_all(self, check):
        """Config deny rule on script blocks everything."""
        config = Config(rules=[Rule("deny", "script", message="no recording")])
        result = check("script -q /dev/null ls", config=config)
        assert not is_approved(result)
