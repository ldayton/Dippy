"""
Ruff command handler for Dippy.

Ruff is a Python linter/formatter. Most commands are safe,
but "ruff clean" modifies files by removing cached data.
"""

COMMANDS = ["ruff"]

UNSAFE_ACTIONS = frozenset(
    {
        "clean",  # Removes cache files
    }
)


def check(tokens: list[str]) -> bool:
    """Check if ruff command is safe (not clean)."""
    if len(tokens) < 2:
        return True  # Just "ruff" shows help

    action = tokens[1]
    return action not in UNSAFE_ACTIONS
