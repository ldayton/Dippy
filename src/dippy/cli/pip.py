"""
Python package manager CLI handler for Dippy.

Handles pip, pip3, and uv commands.
"""

from typing import Optional


SAFE_ACTIONS = frozenset({
    "list", "freeze", "show",
    "search",  # Deprecated but safe
    "check", "config",
    "help", "-h", "--help",
    "version", "-V", "--version",
    "debug", "cache",
    "index",
})


UNSAFE_ACTIONS = frozenset({
    "install", "uninstall", "remove",
    "download",
    "wheel",
    "hash",
})


SAFE_SUBCOMMANDS = {
    "cache": {"dir", "info", "list"},
    "config": {"list", "get", "debug"},
    # uv specific
    "pip": {"list", "freeze", "show", "check"},
}


UNSAFE_SUBCOMMANDS = {
    "cache": {"purge", "remove"},
    "config": {"set", "unset"},
    "pip": {"install", "uninstall"},
}


def check(command: str, tokens: list[str]) -> Optional[str]:
    """Check if a pip/uv command should be approved or denied."""
    if len(tokens) < 2:
        return None
    
    base = tokens[0]
    action = tokens[1]
    rest = tokens[2:] if len(tokens) > 2 else []
    
    # Handle uv which wraps pip
    if base == "uv":
        if action == "pip":
            # Treat rest as pip command
            if rest:
                action = rest[0]
                rest = rest[1:] if len(rest) > 1 else []
            else:
                return None
        elif action in {"run", "tool", "sync", "lock", "add", "remove"}:
            return None  # uv-specific unsafe commands
        elif action in {"version", "--version", "-V", "help", "--help"}:
            return "approve"
    
    # Check subcommands
    if action in SAFE_SUBCOMMANDS and rest:
        for token in rest:
            if not token.startswith("-"):
                if token in SAFE_SUBCOMMANDS[action]:
                    return "approve"
                break
    
    if action in UNSAFE_SUBCOMMANDS and rest:
        for token in rest:
            if not token.startswith("-"):
                if token in UNSAFE_SUBCOMMANDS[action]:
                    return None
                break
    
    if action in SAFE_ACTIONS:
        return "approve"
    
    if action in UNSAFE_ACTIONS:
        return None
    
    return None
