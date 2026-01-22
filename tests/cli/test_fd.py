"""Test cases for fd."""

from __future__ import annotations

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Safe operations - basic searches
    ("fd", True),
    ("fd pattern", True),
    ("fd pattern path/to/dir", True),
    ("fd -e txt", True),
    ("fd --extension py", True),
    # Safe operations - with various flags
    ("fd -H pattern", True),
    ("fd --hidden pattern", True),
    ("fd -I pattern", True),
    ("fd --no-ignore pattern", True),
    ("fd -u pattern", True),
    ("fd --unrestricted pattern", True),
    ("fd -t f pattern", True),
    ("fd --type file pattern", True),
    ("fd -t d pattern", True),
    ("fd --type directory pattern", True),
    ("fd -d 3 pattern", True),
    ("fd --max-depth 3 pattern", True),
    ("fd -E node_modules pattern", True),
    ("fd --exclude '*.pyc' pattern", True),
    ("fd -a pattern", True),
    ("fd --absolute-path pattern", True),
    ("fd -l pattern", True),
    ("fd --list-details pattern", True),
    ("fd -L pattern", True),
    ("fd --follow pattern", True),
    ("fd -p pattern", True),
    ("fd --full-path pattern", True),
    ("fd -g pattern", True),
    ("fd --glob pattern", True),
    ("fd -s pattern", True),
    ("fd --case-sensitive pattern", True),
    ("fd -i pattern", True),
    ("fd --ignore-case pattern", True),
    ("fd -S +1m pattern", True),
    ("fd --size +1m pattern", True),
    ("fd --changed-within 1week pattern", True),
    ("fd --changed-before 2024-01-01 pattern", True),
    ("fd -0 pattern", True),
    ("fd --print0 pattern", True),
    ("fd -q pattern", True),
    ("fd --quiet pattern", True),
    ("fd --help", True),
    ("fd -h", True),
    ("fd --version", True),
    ("fd -V", True),
    # Unsafe operations - execute commands with unsafe inner commands
    ("fd -x rm", False),
    ("fd --exec rm", False),
    ("fd -X rm", False),
    ("fd --exec-batch rm", False),
    ("fd pattern -X vim", False),
    ("fd pattern --exec-batch vim", False),
    ("fd -e py -x python", False),
    # Safe operations - execute with safe inner commands
    ("fd -x echo", True),
    ("fd --exec echo", True),
    ("fd pattern -x cat", True),
    ("fd pattern --exec cat", True),
    ("fd --type f --exec cat {}", True),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_fd(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
