"""
Journalctl command handler for Dippy.

Journalctl is safe for viewing logs, but modification flags need confirmation.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["journalctl"]

UNSAFE_FLAGS = frozenset(
    {
        "--rotate",
        "--vacuum-time",
        "--vacuum-size",
        "--vacuum-files",
        "--flush",
        "--sync",
        "--relinquish-var",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify journalctl command (no modification flags is safe)."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "journalctl"
    for token in tokens[1:]:
        if token in UNSAFE_FLAGS:
            return Classification("ask", description=f"{base} {token}")
        for flag in UNSAFE_FLAGS:
            if token.startswith(flag + "="):
                return Classification("ask", description=f"{base} {flag}")
    return Classification("allow", description=base)
