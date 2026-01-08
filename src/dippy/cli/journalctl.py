"""
Journalctl command handler for Dippy.

Journalctl is safe for viewing logs, but modification flags need confirmation.
"""

COMMANDS = ["journalctl"]

UNSAFE_FLAGS = frozenset({
    "--rotate",
    "--vacuum-time", "--vacuum-size", "--vacuum-files",
    "--flush",
    "--sync",
    "--relinquish-var",
})


def check(tokens: list[str]) -> bool:
    """Check if journalctl command is safe (no modification flags)."""
    for token in tokens[1:]:
        if token in UNSAFE_FLAGS:
            return False
        for flag in UNSAFE_FLAGS:
            if token.startswith(flag + "="):
                return False
    return True
