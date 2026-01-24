"""Mktemp command handler for Dippy.

mktemp creates temporary files/directories.
-u flag is dry run - just prints a name without creating.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["mktemp"]


def classify(ctx: HandlerContext) -> Classification:
    """Classify mktemp command."""
    tokens = ctx.tokens

    # -u is dry run - doesn't create the file
    if "-u" in tokens:
        return Classification("allow", description="mktemp -u")

    return Classification("ask", description="mktemp")
