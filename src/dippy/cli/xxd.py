"""xxd handler for Dippy.

xxd is a hex dump tool. Safe for reading, but -r (revert) mode writes files.
"""

from dippy.cli import Classification

COMMANDS = ["xxd"]

UNSAFE_FLAGS = frozenset({"-r", "-revert"})


def classify(tokens: list[str]) -> Classification:
    """Classify xxd command."""
    if not tokens:
        return Classification("ask", description="xxd")

    for token in tokens[1:]:
        if token in UNSAFE_FLAGS:
            return Classification("ask", description="xxd -r")

    return Classification("approve", description="xxd")
