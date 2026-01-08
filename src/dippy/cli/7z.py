"""
7z archive command handler for Dippy.

Handles unzip, 7z, 7za, 7zr, 7zz commands.
Read-only operations (list, test, info) are safe, extraction/modification is not.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

# Unzip flags that are safe (read-only operations)
UNZIP_SAFE_FLAGS = frozenset({
    "-l",  # list short format
    "-v",  # verbose list / version info
    "-t",  # test archive integrity
    "-z",  # display archive comment only
    "-Z",  # zipinfo mode (detailed listing)
    "-h",  # help
    "-hh",  # extended help
    "--help",
})

# 7z commands that are safe (read-only operations)
SAFE_7Z_COMMANDS = frozenset({
    "l",  # list contents
    "t",  # test archive integrity
    "h",  # calculate hash
    "b",  # benchmark
    "i",  # show info about supported formats
})


def check_unzip(tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if an unzip command should be approved.

    Safe operations: -l (list), -v (verbose), -t (test), -z (comment), -Z (zipinfo)

    Returns:
        "approve" - Read-only operation
        None - Extract mode, needs confirmation
    """
    # Check for explicit safe flags
    for t in tokens[1:]:
        if t in UNZIP_SAFE_FLAGS:
            return ("approve", "7z")
        # Handle combined short flags like -lv, -tq, -Zl
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            # Check if any safe flag char is present
            for char in t[1:]:
                if f"-{char}" in UNZIP_SAFE_FLAGS or char in "lvtZz":
                    # But not if it has extract-related flags (o=overwrite, d=dir)
                    if any(c in t for c in "od"):
                        return (None, "7z")
                    return ("approve", "7z")
    return (None, "7z")


def check_7z(tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a 7z command should be approved.

    Safe operations: l (list), t (test), h (hash), b (benchmark), i (info)

    Returns:
        "approve" - Read-only operation
        None - Other operations, needs confirmation
    """
    # 7z with no args shows help
    if len(tokens) < 2:
        return ("approve", "7z")

    # Check for help flags
    if tokens[1] in ("--help", "-h"):
        return ("approve", "7z")

    # Check for safe commands
    if tokens[1] in SAFE_7Z_COMMANDS:
        return ("approve", "7z")

    return (None, "7z")


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """Route to appropriate archive handler."""
    if not tokens:
        return (None, "7z")

    cmd = tokens[0]
    if cmd == "unzip":
        return check_unzip(tokens)
    elif cmd in ("7z", "7za", "7zr", "7zz"):
        return check_7z(tokens)

    return (None, "7z")
