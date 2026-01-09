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
    ("uv help sync", True),
    ("uv version", True),
    ("uv --version", True),
    #
    # === SAFE: Project viewing ===
    ("uv sync", True),
    ("uv sync --frozen", True),
    ("uv sync --locked", True),
    ("uv sync --no-install-project", True),
    ("uv lock", True),
    ("uv lock --upgrade", True),
    ("uv lock --locked", True),
    ("uv tree", True),
    ("uv tree --depth 2", True),
    ("uv tree --no-dedupe", True),
    ("uv tree --package requests", True),
    ("uv venv", True),
    ("uv venv .venv", True),
    ("uv venv --python 3.11", True),
    ("uv venv --seed", True),
    #
    # === SAFE: Export (read-only) ===
    ("uv export", True),
    ("uv export --format requirements-txt", True),
    ("uv export --no-dev", True),
    ("uv export --extra test", True),
    ("uv export --all-extras", True),
    ("uv export --no-hashes", True),
    ("uv export -o requirements.txt", True),
    #
    # === SAFE: uv pip viewing ===
    ("uv pip", True),  # shows help
    ("uv pip list", True),
    ("uv pip list --format json", True),
    ("uv pip list --outdated", True),
    ("uv pip freeze", True),
    ("uv pip freeze --strict", True),
    ("uv pip show requests", True),
    ("uv pip show --files requests", True),
    ("uv pip check", True),
    ("uv pip tree", True),
    #
    # === SAFE: Cache viewing ===
    ("uv cache dir", True),
    #
    # === SAFE: Python viewing ===
    ("uv python list", True),
    ("uv python list --all-versions", True),
    ("uv python find", True),
    ("uv python find 3.11", True),
    ("uv python dir", True),
    #
    # === SAFE: uv run with safe inner commands ===
    ("uv run ls", True),
    ("uv run pwd", True),
    ("uv run echo hello", True),
    ("uv run python --version", True),
    ("uv run git status", True),
    ("uv run --with requests ls", True),
    ("uv run --python 3.11 ls", True),
    ("uv run --frozen ls", True),
    #
    # === UNSAFE: uv pip install/uninstall ===
    ("uv pip install requests", False),
    ("uv pip install -r requirements.txt", False),
    ("uv pip install --upgrade requests", False),
    ("uv pip install -e .", False),
    ("uv pip uninstall requests", False),
    ("uv pip uninstall -y requests", False),
    ("uv pip sync requirements.txt", False),
    ("uv pip compile requirements.in", False),
    #
    # === UNSAFE: Project modification ===
    ("uv add requests", False),
    ("uv add requests numpy", False),
    ("uv add --dev pytest", False),
    ("uv add --optional test pytest", False),
    ("uv add --group dev pytest", False),
    ("uv remove requests", False),
    ("uv remove --dev pytest", False),
    ("uv init", False),
    ("uv init myproject", False),
    ("uv init --lib mylib", False),
    ("uv build", False),
    ("uv build --wheel", False),
    ("uv build --sdist", False),
    ("uv publish", False),
    ("uv publish --token TOKEN", False),
    #
    # === UNSAFE: Cache modification ===
    ("uv cache clean", False),
    ("uv cache clean requests", False),
    ("uv cache prune", False),
    ("uv cache prune --ci", False),
    #
    # === UNSAFE: Python management ===
    ("uv python install 3.12", False),
    ("uv python install 3.11 3.12", False),
    ("uv python uninstall 3.12", False),
    ("uv python pin 3.12", False),
    ("uv python pin --resolved 3.12", False),
    #
    # === SAFE: uv run with safe tools ===
    ("uv run pytest", True),
    ("uv run pytest -v tests/", True),
    ("uv run ruff check", True),
    ("uv run ruff format", True),
    ("uv run mypy .", True),
    #
    # === UNSAFE: uv run with unsafe inner commands ===
    ("uv run rm file.txt", False),
    ("uv run npm install", False),
    ("uv run pip install requests", False),
    ("uv run python script.py", False),
    ("uv run --with requests python script.py", False),
    ("uv run bash -c 'echo hello'", False),
    ("uv run sh -c 'ls'", False),
    ("uv run node script.js", False),
    ("uv run make build", False),
    #
    # === UNSAFE: uv tool ===
    ("uv tool run ruff check", False),
    ("uv tool run --from ruff ruff check", False),
    ("uv tool install ruff", False),
    ("uv tool uninstall ruff", False),
    ("uv tool upgrade ruff", False),
    (
        "uv tool list",
        False,
    ),  # uv tool list shows installed tools but tool commands are unsafe
    ("uv tool dir", False),
    #
    # === UNSAFE: uvx (alias for uv tool run) ===
    ("uvx ruff check", False),
    ("uvx --from ruff ruff check", False),
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
