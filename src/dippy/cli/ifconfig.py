"""
Ifconfig command handler for Dippy.

Ifconfig is safe for viewing, but modification commands need confirmation.
"""

from dippy.cli import Classification

COMMANDS = ["ifconfig"]


def classify(tokens: list[str]) -> Classification:
    """Classify ifconfig command (viewing only is safe)."""
    base = tokens[0] if tokens else "ifconfig"
    # "ifconfig" or "ifconfig -a" or "ifconfig eth0" are safe
    # Any additional args beyond interface name is a modification
    if len(tokens) <= 2:
        return Classification("approve", description=base)
    return Classification("ask", description=base)
