"""
Tar command handler for Dippy.

Tar can list, create, or extract archives.
Only listing (-t/--list) is safe.
"""

from dippy.cli import Classification

COMMANDS = ["tar"]


def classify(tokens: list[str]) -> Classification:
    """Classify tar command (list mode only is safe)."""
    base = tokens[0] if tokens else "tar"
    for t in tokens[1:]:
        if t == "-t" or t == "--list":
            return Classification("approve", description=f"{base} list")
        # Combined short flags like -tvf, -tf, -ztf
        if t.startswith("-") and not t.startswith("--") and "t" in t:
            return Classification("approve", description=f"{base} list")

    # Old-style (no dash) like "tf", "tvf", "ztf"
    if len(tokens) > 1:
        first_arg = tokens[1]
        if (
            not first_arg.startswith("-")
            and "t" in first_arg
            and not any(c in first_arg for c in "cxru")
        ):
            return Classification("approve", description=f"{base} list")

    return Classification("ask", description=base)
