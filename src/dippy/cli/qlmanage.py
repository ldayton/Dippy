"""
Qlmanage command handler for Dippy.

macOS Quick Look Server debug and management tool.
- -m (info), -t (thumbnails), -p (previews), -h (help) are safe
- -r resets Quick Look Server (modifies system state)
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["qlmanage"]

# Safe read-only/display operations
SAFE_FLAGS = frozenset({"-m", "-t", "-p", "-h"})

# Flags that modify system state
UNSAFE_FLAGS = frozenset({"-r"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify qlmanage command."""
    tokens = ctx.tokens
    for t in tokens[1:]:
        if t in UNSAFE_FLAGS:
            return Classification("ask", description=f"qlmanage {t}")
        if t in SAFE_FLAGS:
            return Classification("allow", description=f"qlmanage {t}")
    # No recognized flag, default to allow (probably -h behavior)
    return Classification("allow", description="qlmanage")
