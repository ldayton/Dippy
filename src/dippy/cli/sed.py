"""
Sed command handler for Dippy.

Sed is safe for text processing, but -i flag modifies files in place.
"""

COMMANDS = ["sed"]


def check(tokens: list[str]) -> bool:
    """Check if sed command is safe (no in-place modification)."""
    for t in tokens[1:]:
        if t == "-i" or t.startswith("-i"):
            return False
        if t == "--in-place" or t.startswith("--in-place"):
            return False
    return True
