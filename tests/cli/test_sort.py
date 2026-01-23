"""
Comprehensive tests for sort CLI handler.

Sort is safe for text processing, but -o flag writes to a file.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation
from dippy.core.config import Config, Rule


TESTS = [
    # === SAFE: Read-only sorting ===
    ("sort file.txt", True),
    ("sort -r file.txt", True),  # reverse
    ("sort --reverse file.txt", True),
    ("sort -n file.txt", True),  # numeric
    ("sort --numeric-sort file.txt", True),
    ("sort -h file.txt", True),  # human numeric
    ("sort --human-numeric-sort file.txt", True),
    ("sort -u file.txt", True),  # unique
    ("sort --unique file.txt", True),
    ("sort -k2 file.txt", True),  # key
    ("sort --key=2 file.txt", True),
    ("sort -k2,2 file.txt", True),
    ("sort -k2n file.txt", True),  # numeric key
    ("sort -t: file.txt", True),  # delimiter
    ("sort --field-separator=: file.txt", True),
    ("sort -f file.txt", True),  # ignore case
    ("sort --ignore-case file.txt", True),
    ("sort -b file.txt", True),  # ignore leading blanks
    ("sort --ignore-leading-blanks file.txt", True),
    ("sort -d file.txt", True),  # dictionary order
    ("sort --dictionary-order file.txt", True),
    ("sort -i file.txt", True),  # ignore nonprinting
    ("sort --ignore-nonprinting file.txt", True),
    ("sort -M file.txt", True),  # month sort
    ("sort --month-sort file.txt", True),
    ("sort -V file.txt", True),  # version sort
    ("sort --version-sort file.txt", True),
    ("sort -c file.txt", True),  # check sorted
    ("sort --check file.txt", True),
    ("sort -C file.txt", True),  # check quietly
    ("sort --check=quiet file.txt", True),
    ("sort -m file1.txt file2.txt", True),  # merge
    ("sort --merge file1.txt file2.txt", True),
    ("sort -s file.txt", True),  # stable
    ("sort --stable file.txt", True),
    ("sort -z file.txt", True),  # null terminated
    ("sort --zero-terminated file.txt", True),
    ("sort -R file.txt", True),  # random
    ("sort --random-sort file.txt", True),
    ("sort -T /tmp file.txt", True),  # temp directory
    ("sort --temporary-directory=/tmp file.txt", True),
    ("sort -S 100M file.txt", True),  # buffer size
    ("sort --buffer-size=100M file.txt", True),
    ("sort --parallel=4 file.txt", True),
    ("sort < file.txt", True),  # stdin
    ("sort -n -r -u file.txt", True),  # multiple flags
    ("sort -nru file.txt", True),  # combined flags
    ("sort file1.txt file2.txt file3.txt", True),  # multiple files
    #
    # === UNSAFE: Output to file ===
    ("sort -o output.txt file.txt", False),
    ("sort --output output.txt file.txt", False),
    ("sort --output=output.txt file.txt", False),
    ("sort -ooutput.txt file.txt", False),  # no space
    ("sort file.txt -o output.txt", False),  # -o in middle
    ("sort -n -o output.txt file.txt", False),  # with other flags
    ("sort -u -o sorted.txt file.txt", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"


class TestSortWithRedirectRules:
    """sort -o should respect redirect rules for the output file."""

    def test_sort_output_allowed_by_rule(self, check, tmp_path):
        """sort -o to allowed path should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("sort -o /tmp/out.txt input.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_sort_output_denied_by_rule(self, check, tmp_path):
        """sort -o to denied path should be denied."""
        cfg = Config(redirect_rules=[Rule("deny", "/etc/*")])
        result = check("sort -o /etc/passwd input.txt", config=cfg, cwd=tmp_path)
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    def test_sort_output_long_flag_allowed(self, check, tmp_path):
        """sort --output to allowed path should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("sort --output /tmp/out.txt input.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_sort_output_equals_allowed(self, check, tmp_path):
        """sort --output=file to allowed path should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("sort --output=/tmp/out.txt input.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)

    def test_sort_output_no_space_allowed(self, check, tmp_path):
        """sort -ofile to allowed path should be approved."""
        cfg = Config(redirect_rules=[Rule("allow", "/tmp/*")])
        result = check("sort -o/tmp/out.txt input.txt", config=cfg, cwd=tmp_path)
        assert is_approved(result)
