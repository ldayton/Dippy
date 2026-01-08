"""
IP command handler for Dippy.

The ip command is safe for viewing network info, but modification
commands need confirmation.
"""

from typing import Optional


# Safe ip subcommands (read-only)
SAFE_SUBCOMMANDS = frozenset({
    "addr", "address", "a",  # "a" is common alias for addr
    "link", "l",  # "l" is alias for link
    "route", "r",
    "rule", "ru",  # "ru" is alias for rule
    "neigh", "neighbor", "n",  # "n" is alias for neigh
    "tunnel",
    "tuntap", "tunt",  # "tunt" is alias for tuntap
    "maddr", "maddress", "m",  # "m" is alias for maddress
    "mroute",
    "monitor", "mo",  # "mo" is alias for monitor
    "netns",
    "netconf", "netc",  # network config (read-only)
    "stats", "st",  # interface statistics (read-only)
})

# Subcommand actions that modify state
MODIFY_ACTIONS = frozenset({
    "add", "del", "delete", "change", "replace",
    "set", "flush",
    "exec",  # ip netns exec
})

# Global flags that take an argument (need to skip)
GLOBAL_FLAGS_WITH_ARG = frozenset({
    "-n", "-netns", "--netns",
    "-b", "-batch", "--batch",
    "-rc", "-rcvbuf", "--rcvbuf",
})


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if an ip command should be approved.

    Returns:
        "approve" - Read-only operation
        None - Modification command, needs confirmation
    """
    if len(tokens) < 2:
        return (None, "ip")

    # Find subcommand and actions, skipping global flags with arguments
    parts = []
    i = 1
    while i < len(tokens):
        token = tokens[i]
        # Skip global flags that take an argument
        if token in GLOBAL_FLAGS_WITH_ARG:
            i += 2  # Skip flag and its argument
            continue
        # Skip other flags
        if token.startswith("-"):
            i += 1
            continue
        parts.append(token)
        i += 1

    if not parts:
        return ("approve", "ip")  # Just "ip" or "ip -flags"

    subcommand = parts[0]

    # Check if there's a modifying action
    for part in parts[1:]:
        if part in MODIFY_ACTIONS:
            return (None, "ip")

    # "ip addr" (show), "ip route" (show), etc. are safe
    if subcommand in SAFE_SUBCOMMANDS:
        return ("approve", "ip")

    return (None, "ip")
