"""
Tar command handler for Dippy.

Tar can list, create, or extract archives.
Only listing (-t/--list) is safe.
"""

from dippy.cli import Classification

COMMANDS = ["tar"]

# Map operation flags to human-readable names
OPERATIONS = {
    "c": "create",
    "x": "extract",
    "r": "append",
    "u": "update",
    "t": "list",
}


def _detect_operation(tokens: list[str]) -> str | None:
    """Detect which tar operation is being performed."""
    for t in tokens[1:]:
        # Long flags
        if t == "--create":
            return "create"
        if t == "--extract" or t == "--get":
            return "extract"
        if t == "--append":
            return "append"
        if t == "--update":
            return "update"
        if t == "--list":
            return "list"
        if t == "--delete":
            return "delete"
        # Short flags (could be combined like -cvf, -xzf)
        if t.startswith("-") and not t.startswith("--"):
            for char, op in OPERATIONS.items():
                if char in t:
                    return op
    # Old-style (no dash) like "cvf", "xzf"
    if len(tokens) > 1:
        first_arg = tokens[1]
        if not first_arg.startswith("-"):
            for char, op in OPERATIONS.items():
                if char in first_arg:
                    return op
    return None


def classify(tokens: list[str]) -> Classification:
    """Classify tar command (list mode only is safe)."""
    base = tokens[0] if tokens else "tar"
    operation = _detect_operation(tokens)
    if operation == "list":
        return Classification("approve", description=f"{base} list")
    if operation:
        return Classification("ask", description=f"{base} {operation}")
    return Classification("ask", description=base)
