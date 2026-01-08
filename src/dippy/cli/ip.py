"""
IP command handler for Dippy.

The ip command is safe for viewing network info, but modification
commands need confirmation.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

# Safe ip subcommands (read-only)
SAFE_SUBCOMMANDS = frozenset({
    "addr", "address",
    "link",
    "route", "r",
    "rule",
    "neigh", "neighbor",
    "tunnel",
    "tuntap",
    "maddr", "maddress",
    "mroute",
    "monitor",
    "netns",
})

# Subcommand actions that modify state
MODIFY_ACTIONS = frozenset({
    "add", "del", "delete", "change", "replace",
    "set", "up", "down", "flush",
    "exec",  # ip netns exec
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if an ip command should be approved.

    Returns:
        "approve" - Read-only operation
        None - Modification command, needs confirmation
    """
    if len(tokens) < 2:
        return None

    # Find subcommand and action
    parts = [t for t in tokens[1:] if not t.startswith("-")]

    if not parts:
        return "approve"  # Just "ip" or "ip -flags"

    subcommand = parts[0]

    # Check if there's a modifying action
    for part in parts[1:]:
        if part in MODIFY_ACTIONS:
            return None

    # "ip addr" (show), "ip route" (show), etc. are safe
    if subcommand in SAFE_SUBCOMMANDS:
        return "approve"

    return None
