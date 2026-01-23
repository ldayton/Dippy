"""
Comprehensive tests for sed CLI handler.

Sed is safe for text processing, but has several unsafe operations:
- -i flag modifies files in place
- w command writes to files (e.g., s/foo/bar/w output.txt)
- e command (GNU sed) executes pattern space as shell command
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation
from dippy.core.config import Config, Rule


TESTS = [
    # === SAFE: Read-only text processing ===
    ("sed 's/foo/bar/' file.txt", True),
    ("sed 's/foo/bar/g' file.txt", True),
    ("sed '/pattern/d' file.txt", True),
    ("sed '/pattern/p' file.txt", True),
    ("sed -n '/pattern/p' file.txt", True),
    ("sed -n '1,10p' file.txt", True),
    ("sed '1,10d' file.txt", True),
    ("sed '$d' file.txt", True),
    ("sed 's/foo/bar/' < file.txt", True),
    ("sed -e 's/foo/bar/' -e 's/baz/qux/' file.txt", True),
    ("sed -E 's/[0-9]+/NUM/' file.txt", True),
    ("sed -r 's/[0-9]+/NUM/' file.txt", True),  # GNU sed
    ("sed --regexp-extended 's/[0-9]+/NUM/' file.txt", True),
    ("sed -f script.sed file.txt", True),
    ("sed --file=script.sed file.txt", True),
    ("sed -n 's/pattern/replacement/p' file.txt", True),
    ("sed 'y/abc/xyz/' file.txt", True),  # transliterate
    ("sed '/start/,/end/d' file.txt", True),  # range delete
    ("sed '1!G;h;$!d' file.txt", True),  # reverse lines (tac)
    ("sed ':a;N;$!ba;s/\\n/ /g' file.txt", True),  # join lines
    #
    # === UNSAFE: In-place modification ===
    ("sed -i 's/foo/bar/' file.txt", False),
    ("sed -i.bak 's/foo/bar/' file.txt", False),
    ("sed -i '' 's/foo/bar/' file.txt", False),  # macOS no backup
    ("sed -i's/foo/bar/' file.txt", False),  # no space
    ("sed -i.bak 's/foo/bar/' *.txt", False),  # multiple files
    ("sed --in-place 's/foo/bar/' file.txt", False),
    ("sed --in-place=.bak 's/foo/bar/' file.txt", False),
    ("sed -i -e 's/foo/bar/' -e 's/baz/qux/' file.txt", False),
    ("sed -e 's/foo/bar/' -i file.txt", False),  # -i anywhere
    ("sed -E -i 's/[0-9]+/NUM/' file.txt", False),
    ("sed -n -i 's/pattern/replacement/p' file.txt", False),
    ("sed -i'' 's/foo/bar/' file.txt", False),  # BSD style
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"


class TestSedInPlaceWithRedirectRules:
    """sed -i should respect redirect rules for the files being modified."""

    def test_sed_inplace_allowed_by_rule(self, check, tmp_path):
        """sed -i on path allowed by redirect rule should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("sed -i 's/foo/bar/' /tmp/file.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_sed_inplace_denied_by_rule(self, check, tmp_path):
        """sed -i on path denied by redirect rule should be denied."""
        cfg = Config(redirect_rules=[Rule("deny", "/etc/*")])
        result = check("sed -i 's/foo/bar/' /etc/passwd", config=cfg, cwd=tmp_path)
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    def test_sed_inplace_multiple_files_all_allowed(self, check, tmp_path):
        """sed -i on multiple files all matching rules should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check(
            "sed -i 's/foo/bar/' /tmp/a.txt /tmp/b.txt", config=cfg, cwd=tmp_path
        )
        assert is_approved(result)

    def test_sed_inplace_multiple_files_one_denied(self, check, tmp_path):
        """sed -i on files where one is denied should be denied."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*"), Rule("deny", "/etc/*")])
        result = check(
            "sed -i 's/foo/bar/' /tmp/a.txt /etc/passwd", config=cfg, cwd=tmp_path
        )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    def test_sed_inplace_with_backup_allowed(self, check, tmp_path):
        """sed -i.bak on allowed path should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check(
            "sed -i.bak 's/foo/bar/' /tmp/file.txt", config=cfg, cwd=tmp_path
        )
        assert is_approved(result)


class TestSedWriteCommand:
    """sed w command writes to files and should be detected."""

    def test_sed_write_command_needs_confirmation(self, check):
        """sed with w flag in substitution should need confirmation."""
        result = check("sed 's/foo/bar/w output.txt' input.txt")
        assert needs_confirmation(result)

    def test_sed_write_command_standalone(self, check):
        """sed with standalone w command should need confirmation."""
        result = check("sed '/pattern/w matches.txt' input.txt")
        assert needs_confirmation(result)

    def test_sed_write_command_denied_by_rule(self, check, tmp_path):
        """sed w to denied path should be denied."""
        cfg = Config(redirect_rules=[Rule("deny", "/etc/*")])
        result = check(
            "sed 's/foo/bar/w /etc/config' input.txt", config=cfg, cwd=tmp_path
        )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    def test_sed_write_flag_with_spaces(self, check):
        """sed w flag with path containing spaces should be detected."""
        result = check("sed 's/foo/bar/w output file.txt' input.txt")
        assert needs_confirmation(result)


class TestSedExecuteCommand:
    """GNU sed e command executes pattern space as shell - always unsafe."""

    def test_sed_execute_flag_on_substitute(self, check):
        """sed s///e executes replacement as shell command."""
        result = check("sed 's/foo/ls/e' input.txt")
        assert needs_confirmation(result)

    def test_sed_execute_command_standalone(self, check):
        """sed e command executes pattern space."""
        result = check("sed 'e' input.txt")
        assert needs_confirmation(result)

    def test_sed_execute_with_command(self, check):
        """sed e with explicit command."""
        result = check("sed 'e date' input.txt")
        assert needs_confirmation(result)


class TestSedCombinations:
    """Combined sed operations."""

    def test_sed_inplace_with_write_one_denied(self, check, tmp_path):
        """sed -i allowed but w target denied should be denied."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*"), Rule("deny", "/etc/*")])
        result = check(
            "sed -i 's/foo/bar/w /etc/matches.txt' /tmp/input.txt",
            config=cfg,
            cwd=tmp_path,
        )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"
