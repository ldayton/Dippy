"""
Journalctl command handler for Dippy.

Journalctl is safe for viewing logs, but modification flags need confirmation.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

# Flags that modify journal state (vacuum, rotate, flush)
UNSAFE_FLAGS = frozenset({
    "--rotate",
    "--vacuum-time", "--vacuum-size", "--vacuum-files",
    "--flush",
    "--sync",
    "--relinquish-var",
})


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a journalctl command should be approved.

    Returns:
        "approve" - Read-only operation (viewing logs)
        None - Modification flag present, needs confirmation
    """
    for token in tokens[1:]:
        # Check for unsafe flags (exact match or starts with for =value flags)
        if token in UNSAFE_FLAGS:
            return (None, "journalctl")
        for flag in UNSAFE_FLAGS:
            if token.startswith(flag + "="):
                return (None, "journalctl")

    # No modification flags - safe to view logs
    return ("approve", "journalctl")
