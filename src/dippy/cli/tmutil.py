"""Tmutil command handler for Dippy.

tmutil is the Time Machine utility for managing backups.
help/version/destinationinfo/isexcluded/list*/latest*/machinedirectory/uniquesize/
verifychecksums/compare/calculatedrift are safe.
enable/disable/start/stop/set*/add*/remove*/delete*/restore etc modify state.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["tmutil"]

# Read-only subcommands
SAFE_SUBCOMMANDS = frozenset(
    {
        "help",
        "version",
        "destinationinfo",
        "isexcluded",
        "latestbackup",
        "listbackups",
        "listlocalsnapshotdates",
        "listlocalsnapshots",
        "machinedirectory",
        "uniquesize",
        "verifychecksums",
        "compare",
        "calculatedrift",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify tmutil command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        return Classification("ask", description="tmutil")

    subcommand = tokens[1]

    if subcommand in SAFE_SUBCOMMANDS:
        return Classification("allow", description=f"tmutil {subcommand}")

    return Classification("ask", description="tmutil")
