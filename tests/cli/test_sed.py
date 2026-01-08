"""
Comprehensive tests for sed CLI handler.

Sed is safe for text processing, but -i flag modifies files in place.
"""

import pytest

from conftest import is_approved, needs_confirmation


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
