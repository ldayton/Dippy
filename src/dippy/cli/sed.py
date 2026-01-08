"""
Sed command handler for Dippy.

Sed is safe for text processing, but -i flag modifies files in place.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()


def check(command: str, tokens: list[str]) -> Optional[str]:
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
            return None
        if t == "--in-place" or t.startswith("--in-place"):
            return None

    return "approve"
