"""
Comprehensive tests for uv CLI handler.

UV has safe commands like sync/lock/tree and unsafe ones like pip install.
UV run checks the inner command for safety.
"""

import pytest

from conftest import is_approved, needs_confirmation


TESTS = [
    # === SAFE: Version/help ===
    ("uv", True),  # shows help
    ("uv --help", True),
    ("uv -h", True),
    ("uv help", True),
    ("uv version", True),
    ("uv --version", True),
    #
    # === SAFE: Project commands ===
    ("uv sync", True),
    ("uv sync --frozen", True),
    ("uv lock", True),
    ("uv lock --upgrade", True),
    ("uv tree", True),
    ("uv tree --depth 2", True),
    ("uv venv", True),
    ("uv venv .venv", True),
    ("uv venv --python 3.11", True),
    #
    # === SAFE: uv pip viewing ===
    ("uv pip", True),  # shows help
    ("uv pip list", True),
    ("uv pip list --format json", True),
    ("uv pip freeze", True),
    ("uv pip show requests", True),
    ("uv pip check", True),
    #
    # === SAFE: uv run with safe inner commands ===
    ("uv run ls", True),
    ("uv run pwd", True),
    ("uv run echo hello", True),
    ("uv run python --version", True),
    ("uv run git status", True),
    ("uv run --with requests ls", True),  # with extra packages
    ("uv run --python 3.11 ls", True),
    #
    # === UNSAFE: uv pip install/uninstall ===
    ("uv pip install requests", False),
    ("uv pip install -r requirements.txt", False),
    ("uv pip uninstall requests", False),
    ("uv pip sync requirements.txt", False),
    #
    # === UNSAFE: Project modification ===
    ("uv add requests", False),
    ("uv add requests numpy", False),
    ("uv add --dev pytest", False),
    ("uv remove requests", False),
    ("uv init", False),
    ("uv init myproject", False),
    ("uv build", False),
    ("uv publish", False),
    #
    # === UNSAFE: uv run with unsafe inner commands ===
    ("uv run rm file.txt", False),
    ("uv run npm install", False),
    ("uv run pip install requests", False),
    ("uv run python script.py", False),
    ("uv run --with requests python script.py", False),
    #
    # === UNSAFE: uv tool ===
    ("uv tool run ruff check", False),
    ("uv tool install ruff", False),
    #
    # === UNSAFE: Self management ===
    ("uv self update", False),
]


@pytest.mark.parametrize("command,expected", TESTS)
def test_command(check, command: str, expected: bool) -> None:
    """Test that command safety is detected correctly."""
    result = check(command)
    if expected:
        assert is_approved(result), f"Expected approved for: {command}"
    else:
        assert needs_confirmation(result), f"Expected confirmation for: {command}"
