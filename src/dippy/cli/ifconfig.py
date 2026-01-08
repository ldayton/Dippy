"""
Ifconfig command handler for Dippy.

Ifconfig is safe for viewing, but modification commands need confirmation.
"""

COMMANDS = ["ifconfig"]


def check(tokens: list[str]) -> bool:
    """Check if ifconfig command is safe (viewing only)."""
    # "ifconfig" or "ifconfig -a" or "ifconfig eth0" are safe
    # Any additional args beyond interface name is a modification
    return len(tokens) <= 2
