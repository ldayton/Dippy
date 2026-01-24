"""Mdimport command handler for Dippy.

mdimport imports files to Spotlight index.
-t is test mode (doesn't store), -L/-A/-X list plugins/schema.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["mdimport"]

# Flags that are read-only
SAFE_FLAGS = frozenset({"-t", "-L", "-A", "-X"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify mdimport command."""
    tokens = ctx.tokens

    for flag in SAFE_FLAGS:
        if flag in tokens:
            return Classification("allow", description=f"mdimport {flag}")

    return Classification("ask", description="mdimport")
