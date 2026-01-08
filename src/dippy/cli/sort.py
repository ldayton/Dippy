"""
Sort command handler for Dippy.

Sort is safe for text processing, but -o flag writes to a file.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a sort command should be approved.

    Rejects sort with -o/--output (writes to file).

    Returns:
        "approve" - Read-only text processing
        None - Writes to file, needs confirmation
    """
    for i, t in enumerate(tokens[1:]):
        # -o or -ofile or --output
        if t == "-o" or t.startswith("-o"):
            return (None, "sort")
        if t == "--output" or t.startswith("--output"):
            return (None, "sort")

    return ("approve", "sort")
