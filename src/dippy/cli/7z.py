"""
7z archive command handler for Dippy.

Handles unzip, 7z, 7za, 7zr, 7zz commands.
Read-only operations (list, test, info) are safe, extraction/modification is not.
"""

COMMANDS = ["unzip", "7z", "7za", "7zr", "7zz"]

# Unzip flags that are safe (read-only operations)
UNZIP_SAFE_FLAGS = frozenset(
    {
        "-l",  # list short format
        "-v",  # verbose list / version info
        "-t",  # test archive integrity
        "-z",  # display archive comment only
        "-Z",  # zipinfo mode (detailed listing)
        "-h",  # help
        "-hh",  # extended help
        "--help",
    }
)

# 7z commands that are safe (read-only operations)
SAFE_7Z_COMMANDS = frozenset(
    {
        "l",  # list contents
        "t",  # test archive integrity
        "h",  # calculate hash
        "b",  # benchmark
        "i",  # show info about supported formats
    }
)


def _check_unzip(tokens: list[str]) -> bool:
    """Check if unzip command is safe (listing/testing only)."""
    for t in tokens[1:]:
        if t in UNZIP_SAFE_FLAGS:
            return True
        # Handle combined short flags like -lv, -tq, -Zl
        if t.startswith("-") and not t.startswith("--") and len(t) > 1:
            for char in t[1:]:
                if f"-{char}" in UNZIP_SAFE_FLAGS or char in "lvtZz":
                    # But not if it has extract-related flags (o=overwrite, d=dir)
                    if any(c in t for c in "od"):
                        return False
                    return True
    return False


def _check_7z(tokens: list[str]) -> bool:
    """Check if 7z command is safe (list/test/hash/benchmark/info)."""
    if len(tokens) < 2:
        return True  # Shows help

    if tokens[1] in ("--help", "-h"):
        return True

    return tokens[1] in SAFE_7Z_COMMANDS


def check(tokens: list[str]) -> bool:
    """Check if archive command is safe."""
    if not tokens:
        return False

    cmd = tokens[0]
    if cmd == "unzip":
        return _check_unzip(tokens)
    elif cmd in ("7z", "7za", "7zr", "7zz"):
        return _check_7z(tokens)

    return False
