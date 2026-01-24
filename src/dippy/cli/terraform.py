"""
Terraform command handler for Dippy.

Handles terraform and tofu (OpenTofu) commands.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["terraform", "tf"]

# Safe read-only actions
SAFE_ACTIONS = frozenset(
    {
        "version",
        "help",
        "fmt",  # Formatting (can modify files but typically wanted)
        "validate",  # Syntax check only
        "plan",  # Shows changes without applying
        "show",  # Show state
        "state",  # State inspection (some subcommands are safe)
        "output",  # Show outputs
        "graph",  # Generate dependency graph
        "providers",  # List providers
        "console",  # Interactive console (read-only)
        "workspace",  # Some subcommands are safe
        "get",  # Downloads modules (doesn't modify infra)
        "modules",  # Shows module information
        "metadata",  # Shows metadata (like functions)
        "test",  # Runs tests (doesn't modify infra)
        "refresh",  # Updates state to match real-world (read-only for infra)
    }
)


# Unsafe actions that modify state or require confirmation
UNSAFE_ACTIONS = frozenset(
    {
        "apply",
        "destroy",
        "import",
        "taint",
        "untaint",
        "init",  # Downloads providers/modules, can take a while
        "login",  # Auth management - modifies credentials
        "logout",
    }
)

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


def classify(ctx: HandlerContext) -> Classification:
    """Classify terraform command."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "terraform"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    # Check for -help flag anywhere (common pattern: terraform -help)
    if "-help" in tokens or "--help" in tokens or "-h" in tokens:
        return Classification("allow", description=f"{base} --help")

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
        return Classification("ask", description=base)

    rest = tokens[action_idx + 1 :] if action_idx + 1 < len(tokens) else []
    desc = f"{base} {action}"

    # Check subcommands
    if action in SAFE_SUBCOMMANDS and rest:
        subcommand = _find_subcommand(rest)
        if subcommand:
            sub_desc = f"{desc} {subcommand}"
            if subcommand in SAFE_SUBCOMMANDS[action]:
                return Classification("allow", description=sub_desc)
            if subcommand in UNSAFE_SUBCOMMANDS.get(action, set()):
                return Classification("ask", description=sub_desc)

    if action in UNSAFE_SUBCOMMANDS and rest:
        subcommand = _find_subcommand(rest)
        if subcommand and subcommand in UNSAFE_SUBCOMMANDS[action]:
            return Classification("ask", description=f"{desc} {subcommand}")

    # Simple safe actions
    if action in SAFE_ACTIONS:
        return Classification("allow", description=desc)

    return Classification("ask", description=desc)


def _find_subcommand(rest: list[str]) -> str | None:
    """Find the first non-flag token (the subcommand)."""
    for token in rest:
        if not token.startswith("-"):
            return token
    return None
