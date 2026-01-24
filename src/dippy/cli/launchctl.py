"""Launchctl command handler for Dippy.

launchctl controls Apple's launchd manager for daemons and agents.
list/print*/blame/plist/procinfo/hostinfo/dumpstate/manager*/version/help/getenv are safe.
bootstrap/bootout/enable/disable/start/stop/load/unload/kill etc modify state.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["launchctl"]

# Read-only subcommands
SAFE_SUBCOMMANDS = frozenset(
    {
        "list",
        "print",
        "print-cache",
        "print-disabled",
        "print-token",
        "plist",
        "procinfo",
        "hostinfo",
        "resolveport",
        "blame",
        "dumpstate",
        "dump-xsc",
        "dumpjpcategory",
        "managerpid",
        "manageruid",
        "managername",
        "error",
        "variant",
        "version",
        "help",
        "getenv",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify launchctl command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        return Classification("ask", description="launchctl")

    subcommand = tokens[1]

    if subcommand in SAFE_SUBCOMMANDS:
        return Classification("allow", description=f"launchctl {subcommand}")

    return Classification("ask", description="launchctl")
