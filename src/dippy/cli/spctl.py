"""Spctl command handler for Dippy.

spctl manages the security assessment policy subsystem (Gatekeeper).
--assess/--status/--disable-status are safe read operations.
--global-enable/--global-disable/--add/--remove etc modify policy.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["spctl"]

# Read-only options
SAFE_OPTIONS = frozenset({"--assess", "-a", "--status", "--disable-status"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify spctl command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        return Classification("ask", description="spctl")

    # Check if any safe option is present
    for token in tokens[1:]:
        if token in SAFE_OPTIONS:
            opt_name = token.lstrip("-")
            return Classification("allow", description=f"spctl {opt_name}")

    return Classification("ask", description="spctl")
