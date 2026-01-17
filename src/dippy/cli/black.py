"""black handler for Dippy.

black is a Python code formatter. It modifies files in place by default,
but --check and --diff are read-only modes.
"""

from dippy.cli import Classification

COMMANDS = ["black"]

SAFE_FLAGS = frozenset({"--check", "--diff"})


def classify(tokens: list[str]) -> Classification:
    """Classify black command."""
    if not tokens:
        return Classification("ask", description="black")

    # Check for read-only flags
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return Classification("approve", description=f"black {token}")

    # Default: formats in place
    return Classification("ask", description="black")
