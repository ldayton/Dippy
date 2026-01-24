"""Dscl command handler for Dippy.

dscl is the Directory Service command line utility.
read/list/search/diff are safe, create/append/merge/delete/change/passwd are not.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["dscl"]

# Read-only commands (with or without leading dash)
SAFE_COMMANDS = frozenset(
    {
        "read",
        "-read",
        "readall",
        "-readall",
        "readpl",
        "-readpl",
        "readpli",
        "-readpli",
        "list",
        "-list",
        "search",
        "-search",
        "diff",
        "-diff",
    }
)

# Options that appear before the datasource
OPTIONS = frozenset({"-p", "-u", "-P", "-f", "-raw", "-plist", "-url", "-q"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify dscl command."""
    tokens = ctx.tokens

    # Skip options to find datasource and command
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in OPTIONS:
            # -u, -P, -f take an argument
            if token in {"-u", "-P", "-f"}:
                i += 2
            else:
                i += 1
            continue
        break

    # Skip datasource (e.g., ".", "/Local/Default", "localhost")
    if i < len(tokens):
        i += 1

    if i >= len(tokens):
        return Classification("ask", description="dscl")

    command = tokens[i]

    if command in SAFE_COMMANDS:
        cmd_name = command.lstrip("-")
        return Classification("allow", description=f"dscl {cmd_name}")

    return Classification("ask", description="dscl")
