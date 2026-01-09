"""
Dmesg command handler for Dippy.

Dmesg is safe for viewing kernel messages, but -c/--clear clears the ring buffer.
"""

COMMANDS = ["dmesg"]

UNSAFE_FLAGS = frozenset(
    {
        "-c",
        "--clear",
        "-C",
        "--console-off",
        "-D",
        "--console-on",
        "-E",
        "--console-level",
    }
)


def check(tokens: list[str]) -> bool:
    """Check if dmesg command is safe (no modification flags)."""
    for token in tokens[1:]:
        if token in UNSAFE_FLAGS:
            return False
        # Handle combined short flags like -cT
        if token.startswith("-") and not token.startswith("--"):
            for char in token[1:]:
                if f"-{char}" in UNSAFE_FLAGS:
                    return False
    return True
