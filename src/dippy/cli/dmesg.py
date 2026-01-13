"""
Dmesg command handler for Dippy.

Dmesg is safe for viewing kernel messages, but -c/--clear clears the ring buffer.
"""

from dippy.cli import Classification

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


def classify(tokens: list[str]) -> Classification:
    """Classify dmesg command (no modification flags is safe)."""
    base = tokens[0] if tokens else "dmesg"
    for token in tokens[1:]:
        if token in UNSAFE_FLAGS:
            return Classification("ask", description=f"{base} {token}")
        # Handle combined short flags like -cT
        if token.startswith("-") and not token.startswith("--"):
            for char in token[1:]:
                if f"-{char}" in UNSAFE_FLAGS:
                    return Classification("ask", description=f"{base} -{char}")
    return Classification("approve", description=base)
