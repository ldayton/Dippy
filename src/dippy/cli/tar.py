"""
Tar command handler for Dippy.

Tar can list, create, or extract archives.
Only listing (-t/--list) is safe.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if a tar command should be approved.

    Only approves tar with list mode (-t/--list).

    Returns:
        "approve" - List mode (read-only)
        None - Create/extract mode, needs confirmation
    """
    for t in tokens[1:]:
        if t == "-t" or t == "--list":
            return "approve"
        # Check for combined short flags like -tvf, -tf, -ztf
        if t.startswith("-") and not t.startswith("--") and "t" in t:
            return "approve"

    # Check first arg for old-style (no dash) like "tf", "tvf", "ztf"
    if len(tokens) > 1:
        first_arg = tokens[1]
        if (
            not first_arg.startswith("-")
            and "t" in first_arg
            and not any(c in first_arg for c in "cxru")
        ):
            return "approve"

    return None
