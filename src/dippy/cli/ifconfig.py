"""
Ifconfig command handler for Dippy.

Ifconfig is safe for viewing, but modification commands need confirmation.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["ifconfig"]


def classify(ctx: HandlerContext) -> Classification:
    """Classify ifconfig command (viewing only is safe)."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "ifconfig"
    # "ifconfig" or "ifconfig -a" or "ifconfig eth0" are safe
    # Any additional args beyond interface name is a modification
    if len(tokens) <= 2:
        return Classification("allow", description=base)
    return Classification("ask", description=f"{base} (modify interface)")
