"""isort handler for Dippy.

isort is a Python import sorter. It modifies files in place by default,
but --check-only, --check, -c, --diff, -d are read-only modes.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["isort"]

SAFE_FLAGS = frozenset({"--check-only", "--check", "-c", "--diff", "-d"})


def classify(tokens: list[str]) -> Classification:
    """Classify isort command."""
    if not tokens:
        return Classification("ask", description="isort")

    # Check for read-only flags
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return Classification("approve", description=f"isort {token}")

    # Default: sorts in place
    return Classification("ask", description="isort")
