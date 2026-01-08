"""
Dmesg command handler for Dippy.

Dmesg is safe for viewing kernel messages, but -c/--clear clears the ring buffer.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

# Flags that modify the kernel ring buffer
UNSAFE_FLAGS = frozenset({
    "-c", "--clear",
    "-C", "--console-off",
    "-D", "--console-on",
    "-E", "--console-level",
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if a dmesg command should be approved.

    Returns:
        "approve" - Read-only operation (viewing messages)
        None - Modification flag present, needs confirmation
    """
    for token in tokens[1:]:
        if token in UNSAFE_FLAGS:
            return None
        # Handle combined short flags like -cT
        if token.startswith("-") and not token.startswith("--"):
            for char in token[1:]:
                if f"-{char}" in UNSAFE_FLAGS:
                    return None

    # No modification flags - safe to view logs
    return "approve"
