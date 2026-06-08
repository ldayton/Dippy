"""Test cases for rtk (Rust Token Killer) transparent wrapper."""

import pytest
from conftest import is_approved, needs_confirmation

TESTS = [
    # Bare rtk - ask
    ("rtk", False),
    # Version / help - handled by global version/help check
    ("rtk --version", True),
    ("rtk --help", True),
    ("rtk -h", True),
    ("rtk help", True),
    ("rtk version", True),
    # Read-only meta subcommands
    ("rtk gain", True),
    ("rtk gain --history", True),
    ("rtk discover", True),
    # Transparent wrapper - safe inner
    ("rtk ls", True),
    ("rtk ls -la", True),
    ("rtk cat README.md", True),
    ("rtk git status", True),
    ("rtk git log", True),
    ("rtk git log --oneline -5", True),
    # Transparent wrapper - unsafe inner
    ("rtk rm -rf /", False),
    ("rtk git push --force origin main", False),
    ("rtk make", False),
    # proxy escape hatch - delegates to inner
    ("rtk proxy ls", True),
    ("rtk proxy git status", True),
    ("rtk proxy rm -rf /", False),
    # proxy with no inner command - ask
    ("rtk proxy", False),
    # Chained with && still inspects each side
    ("rtk git status && rtk git log --oneline -5", True),
    ("rtk ls && rtk rm foo", False),
    # Piped through another rtk-wrapped command
    ("rtk git log --oneline | rtk head -5", True),
    # Unknown rtk flag - ask
    ("rtk --nonexistent-flag", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool):
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approve: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirm: {command}"
