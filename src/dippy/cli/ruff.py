"""
Ruff command handler for Dippy.

Ruff is a Python linter/formatter. Most commands are safe,
but "ruff clean" modifies files by removing cached data.
"""

from dippy.cli import Classification

COMMANDS = ["ruff"]

UNSAFE_ACTIONS = frozenset(
    {
        "clean",  # Removes cache files
    }
)


def classify(tokens: list[str]) -> Classification:
    """Classify ruff command (not clean is safe)."""
    base = tokens[0] if tokens else "ruff"
    if len(tokens) < 2:
        return Classification("approve", description=base)  # Just "ruff" shows help

    action = tokens[1]
    desc = f"{base} {action}"
    if action in UNSAFE_ACTIONS:
        return Classification("ask", description=desc)
    return Classification("approve", description=desc)
