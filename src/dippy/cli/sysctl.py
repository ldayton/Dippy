"""Sysctl command handler for Dippy.

sysctl reads or writes kernel state.
Reading (no = in args) is safe, writing (= in args or -w/-f flags) is not.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["sysctl"]


def classify(ctx: HandlerContext) -> Classification:
    """Classify sysctl command."""
    tokens = ctx.tokens

    # -w explicitly writes, -f loads from file
    if "-w" in tokens or "-f" in tokens:
        return Classification("ask", description="sysctl write")

    # Check for name=value pattern (write operation)
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        if "=" in token:
            return Classification("ask", description="sysctl write")

    return Classification("allow", description="sysctl")
