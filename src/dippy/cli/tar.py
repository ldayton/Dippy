"""
Tar command handler for Dippy.

Tar can list, create, or extract archives.
Only listing (-t/--list) is safe.
"""


def check(tokens: list[str]) -> bool:
    """Check if tar command is safe (list mode only)."""
    for t in tokens[1:]:
        if t == "-t" or t == "--list":
            return True
        # Combined short flags like -tvf, -tf, -ztf
        if t.startswith("-") and not t.startswith("--") and "t" in t:
            return True

    # Old-style (no dash) like "tf", "tvf", "ztf"
    if len(tokens) > 1:
        first_arg = tokens[1]
        if (
            not first_arg.startswith("-")
            and "t" in first_arg
            and not any(c in first_arg for c in "cxru")
        ):
            return True

    return False
