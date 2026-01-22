"""
Comprehensive tests for ruff CLI handler.

Ruff is mostly safe for linting/formatting, but "ruff clean" removes cache.
"""

from __future__ import annotations

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Version/help ===
    ("ruff", True),  # shows help
    ("ruff --help", True),
    ("ruff -h", True),
    ("ruff help", True),
    ("ruff version", True),
    ("ruff --version", True),
    #
    # === SAFE: Linting ===
    ("ruff check", True),
    ("ruff check .", True),
    ("ruff check src/", True),
    ("ruff check file.py", True),
    ("ruff check src/ tests/", True),
    ("ruff check --select E501", True),
    ("ruff check --ignore E501", True),
    ("ruff check --fix", False),  # modifies code
    ("ruff check --fix-only", False),  # modifies code
    ("ruff check --unsafe-fixes", True),
    ("ruff check --show-fixes", True),
    ("ruff check --diff", True),
    ("ruff check --output-format=json", True),
    ("ruff check --output-format=text", True),
    ("ruff check --statistics", True),
    ("ruff check --watch", True),
    ("ruff check --config ruff.toml", True),
    ("ruff check --extend-select F", True),
    ("ruff check --preview", True),
    ("ruff lint", True),  # alias for check
    ("ruff lint .", True),
    ("ruff lint src/", True),
    #
    # === UNSAFE: Formatting (modifies code) ===
    ("ruff format", False),
    ("ruff format .", False),
    ("ruff format src/", False),
    ("ruff format file.py", False),
    ("ruff format --check", False),  # doesn't modify but same command family
    ("ruff format --diff", False),  # doesn't modify but same command family
    ("ruff format --line-length 100", False),
    ("ruff format --config ruff.toml", False),
    ("ruff format --preview", False),
    #
    # === SAFE: Info commands ===
    ("ruff rule E501", True),
    ("ruff rule --all", True),
    ("ruff rule --output-format json E501", True),
    ("ruff linter", True),
    ("ruff config", True),
    #
    # === UNSAFE: Cache operations ===
    ("ruff clean", False),  # removes cache files
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
