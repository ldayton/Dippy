"""
Dmesg command handler for Dippy.

Dmesg is safe for viewing kernel messages, but -c/--clear clears the ring buffer.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["dmesg"]

UNSAFE_FLAGS = frozenset(
    {
        "-c",
        "--clear",
        "-C",
        "--console-off",
        "-D",
        "--console-on",
        "-E",
        "--console-level",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify dmesg command (no modification flags is safe)."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "dmesg"
    for token in tokens[1:]:
        if token in UNSAFE_FLAGS:
            return Classification("ask", description=f"{base} {token}")
        # Handle combined short flags like -cT
        if token.startswith("-") and not token.startswith("--"):
            for char in token[1:]:
                if f"-{char}" in UNSAFE_FLAGS:
                    return Classification("ask", description=f"{base} -{char}")
    return Classification("allow", description=base)
