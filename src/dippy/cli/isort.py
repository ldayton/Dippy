"""isort handler for Dippy.

isort is a Python import sorter. It modifies files in place by default,
but --check-only, --check, -c, --diff, -d are read-only modes.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["isort"]

SAFE_FLAGS = frozenset({"--check-only", "--check", "-c", "--diff", "-d"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify isort command."""
    tokens = ctx.tokens
    if not tokens:
        return Classification("ask", description="isort")

    # Check for read-only flags
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return Classification("allow", description=f"isort {token}")

    # Default: sorts in place
    return Classification("ask", description="isort")
