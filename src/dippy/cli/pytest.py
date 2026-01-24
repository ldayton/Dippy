"""
Pytest command handler for Dippy.

Pytest runs arbitrary Python code, so test execution requires approval.
Safe operations like --version, --help, --collect-only are auto-approved.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["pytest"]

SAFE_FLAGS = frozenset(
    {
        "--version",
        "-V",
        "--help",
        "-h",
        "--collect-only",
        "--co",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify pytest command."""
    tokens = ctx.tokens
    if len(tokens) < 2:
        return Classification("ask", description="pytest run")

    # Check if any safe flag is present
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return Classification("allow", description=f"pytest {token}")

    return Classification("ask", description="pytest run")
