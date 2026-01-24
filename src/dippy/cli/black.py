"""black handler for Dippy.

black is a Python code formatter. It modifies files in place by default,
but --check and --diff are read-only modes.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["black"]

SAFE_FLAGS = frozenset({"--check", "--diff"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify black command."""
    tokens = ctx.tokens
    if not tokens:
        return Classification("ask", description="black")

    # Check for read-only flags
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return Classification("allow", description=f"black {token}")

    # Default: formats in place
    return Classification("ask", description="black")
