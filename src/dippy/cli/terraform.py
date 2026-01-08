"""
Terraform command handler for Dippy.

Handles terraform and tofu (OpenTofu) commands.
"""

from typing import Optional


# Safe read-only actions
SAFE_ACTIONS = frozenset({
    "version", "help",
    "fmt",      # Formatting (can modify files but typically wanted)
    "validate", # Syntax check only
    "plan",     # Shows changes without applying
    "show",     # Show state
    "state",    # State inspection (some subcommands are safe)
    "output",   # Show outputs
    "graph",    # Generate dependency graph
    "providers", # List providers
    "console",  # Interactive console (read-only)
    "workspace", # Some subcommands are safe
    "get",      # Downloads modules (doesn't modify infra)
    "modules",  # Shows module information
    "metadata", # Shows metadata (like functions)
    "test",     # Runs tests (doesn't modify infra)
    "refresh",  # Updates state to match real-world (read-only for infra)
})


# Unsafe actions that modify state or require confirmation
UNSAFE_ACTIONS = frozenset({
    "apply",
    "destroy",
    "import",
    "taint",
    "untaint",
    "init",     # Downloads providers/modules, can take a while
    "login",    # Auth management - modifies credentials
    "logout",
})


# Safe subcommands
SAFE_SUBCOMMANDS = {
    "state": {"list", "show", "pull"},
    "workspace": {"list", "show", "select"},  # select changes context but not resources
}


# Unsafe subcommands
UNSAFE_SUBCOMMANDS = {
    "state": {"mv", "rm", "push", "replace-provider"},
    "workspace": {"new", "delete"},
}


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a terraform command should be approved or denied.

    Returns:
        (decision, description) where decision is "approve" or None.
    """
    base = tokens[0]  # "terraform" or "tofu"

    if len(tokens) < 2:
        return (None, base)

    # Check for -help flag anywhere (common pattern: terraform -help)
    if "-help" in tokens or "--help" in tokens or "-h" in tokens:
        return ("approve", f"{base} help")

    # Find action (skip global flags)
    action = None
    action_idx = 1

    while action_idx < len(tokens):
        token = tokens[action_idx]

        if token.startswith("-"):
            # Skip flag values for known flags
            if token in {"-chdir", "-var", "-var-file"}:
                action_idx += 2
                continue
            action_idx += 1
            continue

        action = token
        break

    if not action:
        return (None, base)

    desc = f"{base} {action}"
    rest = tokens[action_idx + 1:] if action_idx + 1 < len(tokens) else []

    # Check subcommands
    if action in SAFE_SUBCOMMANDS and rest:
        subcommand = _find_subcommand(rest)
        if subcommand:
            if subcommand in SAFE_SUBCOMMANDS[action]:
                return ("approve", desc)
            if subcommand in UNSAFE_SUBCOMMANDS.get(action, set()):
                return (None, desc)

    if action in UNSAFE_SUBCOMMANDS and rest:
        subcommand = _find_subcommand(rest)
        if subcommand and subcommand in UNSAFE_SUBCOMMANDS[action]:
            return (None, desc)

    # Simple safe actions
    if action in SAFE_ACTIONS:
        return ("approve", desc)

    # Unsafe actions need confirmation
    if action in UNSAFE_ACTIONS:
        return (None, desc)

    # Unknown
    return (None, desc)


def _find_subcommand(rest: list[str]) -> Optional[str]:
    """Find the first non-flag token (the subcommand)."""
    for token in rest:
        if not token.startswith("-"):
            return token
    return None
