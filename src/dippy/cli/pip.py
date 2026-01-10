"""
Python package manager CLI handler for Dippy.

Handles pip, pip3, and uv commands.
"""

from dippy.cli import Classification

COMMANDS = ["pip", "pip3"]

SAFE_ACTIONS = frozenset(
    {
        "list",
        "freeze",
        "show",
        "search",  # Deprecated but safe
        "check",
        "config",
        "help",
        "-h",
        "--help",
        "version",
        "-V",
        "--version",
        "debug",
        "cache",
        "index",
        "inspect",  # Read-only environment inspection
        "hash",  # Read-only hash computation
    }
)


UNSAFE_ACTIONS = frozenset(
    {
        "install",
        "uninstall",
        "remove",
        "download",
        "wheel",
        "lock",  # Experimental lock file creation
    }
)


SAFE_SUBCOMMANDS = {
    "cache": {"dir", "info", "list"},
    "config": {"list", "get", "debug"},
    # uv specific
    "pip": {"list", "freeze", "show", "check"},
}


UNSAFE_SUBCOMMANDS = {
    "cache": {"purge", "remove"},
    "config": {"set", "unset", "edit"},
    "pip": {"install", "uninstall"},
}


def classify(tokens: list[str]) -> Classification:
    """Classify pip command."""
    if len(tokens) < 2:
        base = tokens[0] if tokens else "pip"
        return Classification("ask", description=base)

    base = tokens[0]
    action = tokens[1]
    rest = tokens[2:] if len(tokens) > 2 else []
    desc = f"{base} {action}"

    # Handle uv which wraps pip
    if base == "uv":
        if action == "pip":
            if rest:
                action = rest[0]
                rest = rest[1:] if len(rest) > 1 else []
                desc = f"{base} pip {action}"
            else:
                return Classification("ask", description=desc)
        elif action in {"run", "tool", "sync", "lock", "add", "remove"}:
            return Classification(
                "ask", description=desc
            )  # uv-specific unsafe commands
        elif action in {"version", "--version", "-V", "help", "--help"}:
            return Classification("approve", description=desc)

    # Check subcommands
    if action in SAFE_SUBCOMMANDS and rest:
        for token in rest:
            if not token.startswith("-"):
                if token in SAFE_SUBCOMMANDS[action]:
                    return Classification("approve", description=f"{desc} {token}")
                break

    if action in UNSAFE_SUBCOMMANDS and rest:
        for token in rest:
            if not token.startswith("-"):
                if token in UNSAFE_SUBCOMMANDS[action]:
                    return Classification("ask", description=f"{desc} {token}")
                break

    if action in SAFE_ACTIONS:
        return Classification("approve", description=desc)

    return Classification("ask", description=desc)
