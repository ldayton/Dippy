"""
Ruff command handler for Dippy.

Ruff is a Python linter/formatter. Read-only commands are safe,
but format/clean and --fix modify files.
"""

from dippy.cli import Classification

COMMANDS = ["ruff"]

UNSAFE_ACTIONS = frozenset(
    {
        "format",  # Modifies code
        "clean",  # Removes cache files
    }
)


def classify(tokens: list[str]) -> Classification:
    """Classify ruff command."""
    base = tokens[0] if tokens else "ruff"
    if len(tokens) < 2:
        return Classification("approve", description=base)  # Just "ruff" shows help

    action = tokens[1]
    desc = f"{base} {action}"

    # format and clean are unsafe
    if action in UNSAFE_ACTIONS:
        return Classification("ask", description=desc)

    # --fix and --fix-only flags modify code
    if "--fix" in tokens or "--fix-only" in tokens:
        return Classification("ask", description=f"{desc} --fix")

    return Classification("approve", description=desc)
