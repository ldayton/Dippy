"""Tests for pre-commit CLI handler."""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Help and validation ===
    ("pre-commit", True),  # shows help
    ("pre-commit help", True),
    ("pre-commit validate-config", True),
    ("pre-commit validate-manifest", True),
    #
    # === UNSAFE: Modifies files or hooks ===
    ("pre-commit run", False),
    ("pre-commit run --all-files", False),
    ("pre-commit run --files foo.py", False),
    ("pre-commit install", False),
    ("pre-commit install --hook-type pre-push", False),
    ("pre-commit uninstall", False),
    ("pre-commit autoupdate", False),
    ("pre-commit clean", False),
    ("pre-commit gc", False),
    ("pre-commit migrate-config", False),
    ("pre-commit sample-config", False),
    ("pre-commit try-repo", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
