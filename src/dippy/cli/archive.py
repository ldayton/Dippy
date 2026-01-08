"""
Archive command handler for Dippy.

Handles unzip and 7z commands.
Only listing contents is safe, extraction is not.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()


def check_unzip(tokens: list[str]) -> Optional[str]:
    """
    Check if an unzip command should be approved.

    Only approves unzip with list mode (-l).

    Returns:
        "approve" - List mode (read-only)
        None - Extract mode, needs confirmation
    """
    for t in tokens[1:]:
        if t == "-l":
            return "approve"
        # Combined flags like -lv
        if t.startswith("-") and not t.startswith("--") and "l" in t:
            # But not if it has extract-related flags
            if any(c in t for c in "xod"):
                return None
            return "approve"
    return None


def check_7z(tokens: list[str]) -> Optional[str]:
    """
    Check if a 7z command should be approved.

    Only approves 7z with list command (l).

    Returns:
        "approve" - List mode (read-only)
        None - Other operations, needs confirmation
    """
    if len(tokens) < 2:
        return None
    # 7z l archive.7z - list contents
    return "approve" if tokens[1] == "l" else None


def check(command: str, tokens: list[str]) -> Optional[str]:
    """Route to appropriate archive handler."""
    if not tokens:
        return None

    cmd = tokens[0]
    if cmd == "unzip":
        return check_unzip(tokens)
    elif cmd == "7z" or cmd == "7za" or cmd == "7zr":
        return check_7z(tokens)

    return None
