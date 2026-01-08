"""
Shared test fixtures for Dippy tests.
"""

import json
import pytest


@pytest.fixture
def hook_input():
    """Factory for generating hook input JSON."""
    def _make(command: str) -> str:
        return json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": command}
        })
    return _make


@pytest.fixture
def check():
    """Import and return the check_command function."""
    from dippy.dippy import check_command
    return check_command


@pytest.fixture
def check_single():
    """Import and return the _check_single_command function."""
    from dippy.dippy import _check_single_command
    return _check_single_command


def is_approved(result: dict) -> bool:
    """Check if a hook result is an approval."""
    output = result.get("hookSpecificOutput", {})
    return output.get("permissionDecision") == "allow"


def is_denied(result: dict) -> bool:
    """Check if a hook result is a denial."""
    output = result.get("hookSpecificOutput", {})
    return output.get("permissionDecision") == "deny"


def needs_confirmation(result: dict) -> bool:
    """Check if a hook result requires user confirmation."""
    output = result.get("hookSpecificOutput", {})
    return output.get("permissionDecision") == "ask"
