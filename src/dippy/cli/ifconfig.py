"""
Ifconfig command handler for Dippy.

Ifconfig is safe for viewing, but modification commands need confirmation.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

# Arguments that modify interface state
MODIFY_ARGS = frozenset({
    "up", "down",
    "arp", "-arp",
    "promisc", "-promisc",
    "allmulti", "-allmulti",
    "add", "del",
    "netmask", "broadcast", "pointopoint",
    "hw", "ether",
    "mtu", "txqueuelen",
    "mem_start", "io_addr", "irq", "dma",
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if an ifconfig command should be approved.

    Returns:
        "approve" - Read-only operation (viewing)
        None - Modification command, needs confirmation
    """
    if len(tokens) == 1:
        return "approve"  # Just "ifconfig" shows all interfaces

    # Skip the interface name (tokens[1]) and check remaining args
    args = tokens[2:]
    for i, token in enumerate(args):
        # Check for modification arguments
        if token in MODIFY_ARGS:
            return None

    # ifconfig or ifconfig <interface> or ifconfig <interface> <ip> (no netmask = query)
    return "approve"
