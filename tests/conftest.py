"""
Shared test fixtures for Dippy tests.
"""

import json
from pathlib import Path

import pytest

from dippy.core.config import Config


@pytest.fixture
def hook_input():
    """Factory for generating hook input JSON."""

    def _make(command: str) -> str:
        return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})

    return _make


@pytest.fixture
def check():
    """Return a check_command wrapper with default config and cwd."""
    from dippy.dippy import check_command

    def _check(command: str, config: Config | None = None, cwd: Path | None = None):
        if config is None:
            config = Config()
        if cwd is None:
            cwd = Path.cwd()
        return check_command(command, config, cwd)

    return _check


@pytest.fixture
def check_single():
    """Return an analyze wrapper that returns (decision, reason) tuple."""
    from dippy.core.analyzer import analyze

    def _check(command: str, config: Config | None = None, cwd: Path | None = None):
        if config is None:
            config = Config()
        if cwd is None:
            cwd = Path.cwd()
        result = analyze(command, config, cwd)
        # Map action to old decision format
        decision = (
            "approve"
            if result.action == "allow"
            else ("deny" if result.action == "deny" else None)
        )
        return (decision, result.reason)

    return _check


def is_approved(result: dict) -> bool:
    """Check if a hook result is an approval."""
    output = result.get("hookSpecificOutput", {})
    return output.get("permissionDecision") == "allow"


def needs_confirmation(result: dict) -> bool:
    """Check if a hook result requires user confirmation."""
    output = result.get("hookSpecificOutput", {})
    return output.get("permissionDecision") == "ask"
