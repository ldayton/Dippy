"""
IP command handler for Dippy.

The ip command is safe for viewing network info, but modification
commands need confirmation.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["ip"]

# Safe ip subcommands (read-only)
SAFE_SUBCOMMANDS = frozenset(
    {
        "addr",
        "address",
        "a",  # "a" is common alias for addr
        "link",
        "l",  # "l" is alias for link
        "route",
        "r",
        "rule",
        "ru",  # "ru" is alias for rule
        "neigh",
        "neighbor",
        "n",  # "n" is alias for neigh
        "tunnel",
        "tuntap",
        "tunt",  # "tunt" is alias for tuntap
        "maddr",
        "maddress",
        "m",  # "m" is alias for maddress
        "mroute",
        "monitor",
        "mo",  # "mo" is alias for monitor
        "netns",
        "netconf",
        "netc",  # network config (read-only)
        "stats",
        "st",  # interface statistics (read-only)
    }
)

# Subcommand actions that modify state
MODIFY_ACTIONS = frozenset(
    {
        "add",
        "del",
        "delete",
        "change",
        "replace",
        "set",
        "flush",
        "exec",  # ip netns exec
    }
)

# Global flags that take an argument (need to skip)
GLOBAL_FLAGS_WITH_ARG = frozenset(
    {
        "-n",
        "-netns",
        "--netns",
        "-b",
        "-batch",
        "--batch",
        "-rc",
        "-rcvbuf",
        "--rcvbuf",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify ip command."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "ip"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    parts = []
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in GLOBAL_FLAGS_WITH_ARG:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        parts.append(token)
        i += 1

    if not parts:
        return Classification("allow", description=base)  # Just "ip" or "ip -flags"

    subcommand = parts[0]
    desc = f"{base} {subcommand}"

    # Check if there's a modifying action
    for part in parts[1:]:
        if part in MODIFY_ACTIONS:
            return Classification("ask", description=f"{desc} {part}")

    if subcommand in SAFE_SUBCOMMANDS:
        return Classification("allow", description=desc)
    return Classification("ask", description=desc)
