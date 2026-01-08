"""
Helm command handler for Dippy.

Helm is the Kubernetes package manager. Safe operations are read-only queries
(list, get, show, status, history, search) and dry-run modes. Unsafe operations
mutate cluster state, local files, or remote registries.
"""

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


def check(tokens: list[str]) -> bool:
    """Check if helm command is safe."""
    if len(tokens) < 2:
        return False

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
        return False

    action = tokens[idx]
    rest = tokens[idx + 1 :] if idx + 1 < len(tokens) else []

    # Help and version flags are always safe
    if action in {"-h", "--help", "--version"}:
        return True

    # Check for --help anywhere in the command
    if "-h" in tokens or "--help" in tokens:
        return True

    # Simple safe commands
    if action in SAFE_COMMANDS:
        return True

    # Check for dry-run flag (makes install/upgrade/uninstall/rollback safe)
    if action in {"install", "upgrade", "uninstall", "delete", "del", "un", "rollback"}:
        for t in rest:
            if t == "--dry-run" or t.startswith("--dry-run="):
                return True
        return False

    # Nested commands - check subcommand
    if action in NESTED_COMMANDS:
        # Find the subcommand (skip flags)
        for t in rest:
            if t.startswith("-"):
                continue
            # Found subcommand
            if action in SAFE_SUBCOMMANDS and t in SAFE_SUBCOMMANDS[action]:
                return True
            if action in UNSAFE_SUBCOMMANDS and t in UNSAFE_SUBCOMMANDS[action]:
                return False
            # Unknown subcommand - be safe
            return False
        # No subcommand found
        return False

    # Known unsafe commands
    if action in UNSAFE_COMMANDS:
        return False

    # Unknown command - require confirmation
    return False
