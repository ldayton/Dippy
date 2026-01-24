"""
Helm command handler for Dippy.

Helm is the Kubernetes package manager. Safe operations are read-only queries
(list, get, show, status, history, search) and dry-run modes. Unsafe operations
mutate cluster state, local files, or remote registries.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["helm"]

# Safe top-level commands (read-only)
SAFE_COMMANDS = frozenset(
    {
        "completion",
        "env",
        "get",
        "help",
        "history",
        "lint",
        "list",
        "ls",
        "search",
        "show",
        "inspect",  # alias for show
        "status",
        "template",
        "verify",
        "version",
    }
)

# Unsafe top-level commands (mutate cluster, files, or remote)
UNSAFE_COMMANDS = frozenset(
    {
        "create",
        "install",
        "package",
        "pull",
        "fetch",  # alias for pull
        "push",
        "rollback",
        "test",
        "uninstall",
        "delete",  # alias for uninstall
        "del",  # alias for uninstall
        "un",  # alias for uninstall
        "upgrade",
    }
)

# Short aliases that need expansion for clarity
ACTION_ALIASES = {
    "del": "delete",
    "un": "uninstall",
    "fetch": "pull",
}

# Commands with subcommands that need further inspection
NESTED_COMMANDS = frozenset({"dependency", "dep", "plugin", "registry", "repo"})

# Safe subcommands for nested commands
SAFE_SUBCOMMANDS = {
    "dependency": {"list", "ls"},
    "dep": {"list", "ls"},
    "plugin": {"list", "ls", "verify"},
    "repo": {"list", "ls"},
}

# Unsafe subcommands for nested commands
UNSAFE_SUBCOMMANDS = {
    "dependency": {"build", "update", "up"},
    "dep": {"build", "update", "up"},
    "plugin": {"install", "uninstall", "update", "package"},
    "registry": {"login", "logout"},
    "repo": {"add", "remove", "rm", "update", "up", "index"},
}


def classify(ctx: HandlerContext) -> Classification:
    """Classify helm command."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "helm"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    # Handle global flags before subcommand
    idx = 1
    while idx < len(tokens):
        token = tokens[idx]

        # Skip global flags
        if token.startswith("-"):
            # Flags that take arguments
            if token in {
                "-n",
                "--namespace",
                "--kube-context",
                "--kube-apiserver",
                "--kube-as-user",
                "--kube-ca-file",
                "--kube-token",
                "--kubeconfig",
                "--registry-config",
                "--repository-cache",
                "--repository-config",
                "--content-cache",
                "--burst-limit",
                "--qps",
                "--kube-tls-server-name",
            }:
                idx += 2
                continue
            if token.startswith("--kube-as-group"):
                idx += 2
                continue
            idx += 1
            continue

        # Found the subcommand
        break

    if idx >= len(tokens):
        return Classification("ask", description=base)

    action = tokens[idx]
    rest = tokens[idx + 1 :] if idx + 1 < len(tokens) else []
    desc = f"{base} {action}"

    # Help and version flags are always safe
    if action in {"-h", "--help", "--version"}:
        return Classification("allow", description=desc)

    # Check for --help anywhere in the command
    if "-h" in tokens or "--help" in tokens:
        return Classification("allow", description=f"{base} --help")

    # Simple safe commands
    if action in SAFE_COMMANDS:
        return Classification("allow", description=desc)

    # Check for dry-run flag (makes install/upgrade/uninstall/rollback safe)
    if action in {"install", "upgrade", "uninstall", "delete", "del", "un", "rollback"}:
        display_action = ACTION_ALIASES.get(action, action)
        display_desc = f"{base} {display_action}"
        for t in rest:
            if t == "--dry-run" or t.startswith("--dry-run="):
                return Classification("allow", description=f"{display_desc} --dry-run")
        return Classification("ask", description=display_desc)

    # Nested commands - check subcommand
    if action in NESTED_COMMANDS:
        # Find the subcommand (skip flags)
        for t in rest:
            if t.startswith("-"):
                continue
            # Found subcommand
            nested_desc = f"{desc} {t}"
            if action in SAFE_SUBCOMMANDS and t in SAFE_SUBCOMMANDS[action]:
                return Classification("allow", description=nested_desc)
            if action in UNSAFE_SUBCOMMANDS and t in UNSAFE_SUBCOMMANDS[action]:
                return Classification("ask", description=nested_desc)
            # Unknown subcommand - be safe
            return Classification("ask", description=nested_desc)
        # No subcommand found
        return Classification("ask", description=desc)

    # Known unsafe commands
    if action in UNSAFE_COMMANDS:
        display_action = ACTION_ALIASES.get(action, action)
        return Classification("ask", description=f"{base} {display_action}")

    # Unknown command - require confirmation
    return Classification("ask", description=desc)
