"""
Ruff command handler for Dippy.

Ruff is a Python linter/formatter. Most commands are safe,
but "ruff clean" modifies files by removing cached data.
"""

from typing import Optional


SAFE_ACTIONS = frozenset({
    "check", "lint",
    "format",
    "rule", "linter",
    "config",
    "version", "--version",
    "help", "--help",
})

UNSAFE_ACTIONS = frozenset({
    "clean",  # Removes cache files
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if a ruff command should be approved.

    Returns:
        "approve" - Safe linting/formatting operation
        None - Modification command like clean, needs confirmation
    """
    if len(tokens) < 2:
        return "approve"  # Just "ruff" shows help

    action = tokens[1]

    if action in UNSAFE_ACTIONS:
        return None

    if action in SAFE_ACTIONS:
        return "approve"

    # Default to safe for unknown actions (most are read-only)
    return "approve"
