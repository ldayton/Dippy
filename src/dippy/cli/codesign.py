"""
Codesign command handler for Dippy.

macOS code signing utility.
- -d/--display, -v/--verify, -h, --validate-constraint are safe read operations
- -s/--sign modifies binaries (requires identity argument)
- --remove-signature modifies binaries
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["codesign"]

# Long flags that modify code
UNSAFE_LONG_FLAGS = frozenset({"--sign", "--remove-signature"})

# Single-char flags that modify code
UNSAFE_SHORT_FLAGS = frozenset({"s"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify codesign command."""
    tokens = ctx.tokens
    for t in tokens[1:]:
        if t in UNSAFE_LONG_FLAGS:
            return Classification("ask", description=f"codesign {t}")
        if t == "-s":
            return Classification("ask", description="codesign -s")
        # Handle combined flags like -fs, -vfs, etc.
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            for char in t[1:]:
                if char in UNSAFE_SHORT_FLAGS:
                    return Classification("ask", description=f"codesign -{char}")
    return Classification("allow", description="codesign")
