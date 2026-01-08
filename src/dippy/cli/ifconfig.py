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


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if an ifconfig command should be approved.

    Returns:
        "approve" - Read-only operation (viewing)
        None - Modification command, needs confirmation
    """
    if len(tokens) == 1:
        return ("approve", "ifconfig")  # Just "ifconfig" shows all interfaces

    # ifconfig <interface> is safe (just viewing)
    if len(tokens) == 2:
        # Could be "ifconfig eth0" (safe) or "ifconfig -a" (safe)
        return ("approve", "ifconfig")

    # Any additional arguments beyond interface name is a modification
    # ifconfig eth0 192.168.1.100 - sets IP
    # ifconfig eth0 up/down - changes state
    # etc.
    return (None, "ifconfig")
