"""
Terraform command handler for Dippy.

Handles terraform and tofu (OpenTofu) commands.
"""


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


def check(tokens: list[str]) -> bool:
    """Check if terraform command is safe."""
    if len(tokens) < 2:
        return False

    # Check for -help flag anywhere (common pattern: terraform -help)
    if "-help" in tokens or "--help" in tokens or "-h" in tokens:
        return True

    # Find action (skip global flags)
    action = None
    action_idx = 1

    while action_idx < len(tokens):
        token = tokens[action_idx]

        if token.startswith("-"):
            if token in {"-chdir", "-var", "-var-file"}:
                action_idx += 2
                continue
            action_idx += 1
            continue

        action = token
        break

    if not action:
        return False

    rest = tokens[action_idx + 1:] if action_idx + 1 < len(tokens) else []

    # Check subcommands
    if action in SAFE_SUBCOMMANDS and rest:
        subcommand = _find_subcommand(rest)
        if subcommand:
            if subcommand in SAFE_SUBCOMMANDS[action]:
                return True
            if subcommand in UNSAFE_SUBCOMMANDS.get(action, set()):
                return False

    if action in UNSAFE_SUBCOMMANDS and rest:
        subcommand = _find_subcommand(rest)
        if subcommand and subcommand in UNSAFE_SUBCOMMANDS[action]:
            return False

    # Simple safe actions
    if action in SAFE_ACTIONS:
        return True

    # Unsafe actions or unknown
    return False


def _find_subcommand(rest: list[str]) -> str | None:
    """Find the first non-flag token (the subcommand)."""
    for token in rest:
        if not token.startswith("-"):
            return token
    return None
