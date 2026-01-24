"""
Xattr command handler for Dippy.

macOS extended attributes utility.
- -p (print) and -l (list) are safe read operations
- -w (write), -d (delete), -c (clear) modify file metadata
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["xattr"]

# Flags that modify attributes
UNSAFE_FLAGS = frozenset({"-w", "-d", "-c"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify xattr command."""
    tokens = ctx.tokens
    for t in tokens[1:]:
        if t in UNSAFE_FLAGS:
            return Classification("ask", description=f"xattr {t}")
        # Handle combined flags like -wd
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            for char in t[1:]:
                if char in ("w", "d", "c"):
                    return Classification("ask", description=f"xattr -{char}")
    return Classification("allow", description="xattr")
