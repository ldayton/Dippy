"""Profiles command handler for Dippy.

profiles manages configuration and provisioning profiles on macOS.
help/status/list/show/validate/version are safe read operations.
remove/sync/renew modify installed profiles.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["profiles"]

# Read-only subcommands
SAFE_SUBCOMMANDS = frozenset({
    "help",
    "status",
    "list",
    "show",
    "validate",
    "version",
})


def classify(ctx: HandlerContext) -> Classification:
    """Classify profiles command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        return Classification("ask", description="profiles")

    subcommand = tokens[1]

    if subcommand in SAFE_SUBCOMMANDS:
        return Classification("allow", description=f"profiles {subcommand}")

    return Classification("ask", description="profiles")
