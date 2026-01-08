"""
Sed command handler for Dippy.

Sed is safe for text processing, but -i flag modifies files in place.
"""

from typing import Optional


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a sed command should be approved.

    Rejects sed with -i/--in-place (modifies files).

    Returns:
        "approve" - Read-only text processing
        None - Modifies files, needs confirmation
    """
    for t in tokens[1:]:
        # -i or -i'' or -i.bak
        if t == "-i" or t.startswith("-i"):
            return (None, "sed")
        if t == "--in-place" or t.startswith("--in-place"):
            return (None, "sed")

    return ("approve", "sed")
