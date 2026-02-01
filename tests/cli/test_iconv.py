"""Test cases for iconv."""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation
from dippy.core.config import Config, Rule

TESTS = [
    # Safe operations (read-only, output to stdout)
    ("iconv --help", True),
    ("iconv --version", True),
    ("iconv -l", True),
    ("iconv --list", True),
    ("iconv -f UTF-8 -t ASCII input.txt", True),
    ("iconv --from-code=UTF-8 --to-code=ASCII input.txt", True),
    ("iconv -f ISO-8859-1 -t UTF-8 file.txt", True),
    ("iconv -c -f UTF-8 -t ASCII input.txt", True),  # omit invalid chars
    ("iconv -s -f UTF-8 -t ASCII input.txt", True),  # silent mode
    ("iconv --silent -f UTF-8 -t ASCII input.txt", True),
    ("iconv --verbose -f UTF-8 -t ASCII input.txt", True),
    # Unsafe operations (writes to file)
    ("iconv -f UTF-8 -t ASCII -o output.txt input.txt", False),
    ("iconv -f UTF-8 -t ASCII --output=output.txt input.txt", False),
    ("iconv -f UTF-8 -t ASCII --output output.txt input.txt", False),
    ("iconv -ooutput.txt -f UTF-8 -t ASCII input.txt", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"


class TestIconvOutputWithRules:
    """iconv -o should respect redirect rules."""

    def test_iconv_output_allowed_by_rule(self, check, tmp_path):
        """iconv -o to allowed path should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check(
            "iconv -f UTF-8 -t ASCII -o /tmp/output.txt input.txt",
            config=cfg,
            cwd=tmp_path,
        )
        assert is_approved(result)

    def test_iconv_output_denied_by_rule(self, check, tmp_path):
        """iconv -o to denied path should be denied."""
        cfg = Config(redirect_rules=[Rule("deny", "/etc/*")])
        result = check(
            "iconv -f UTF-8 -t ASCII -o /etc/output.txt input.txt",
            config=cfg,
            cwd=tmp_path,
        )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    def test_iconv_output_to_dev_null(self, check):
        """iconv -o to /dev/null should be approved."""
        result = check("iconv -f UTF-8 -t ASCII -o /dev/null input.txt")
        assert is_approved(result)
