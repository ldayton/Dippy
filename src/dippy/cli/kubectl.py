"""
Kubectl command handler for Dippy.

Handles kubectl and similar Kubernetes CLI tools.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["kubectl", "k"]

# Safe read-only actions
SAFE_ACTIONS = frozenset(
    {
        "get",
        "describe",
        "explain",
        "logs",
        "top",
        "cluster-info",
        "version",
        "api-resources",
        "api-versions",
        "config",  # Most config operations are read-only
        "auth",  # auth can-i is read-only
        "wait",  # Polling is read-only
        "diff",  # Shows differences without applying
        "plugin",  # Plugin management (list is read-only)
        "completion",  # Shell completion scripts
        "kustomize",  # Build kustomize manifests (output only)
    }
)


# Unsafe actions that modify cluster state
UNSAFE_ACTIONS = frozenset(
    {
        "create",
        "apply",
        "delete",
        "replace",
        "patch",
        "edit",
        "set",
        "scale",
        "autoscale",
        "rollout",
        "expose",
        "run",
        "attach",
        "exec",  # exec can modify
        "cp",
        "label",
        "annotate",
        "taint",
        "cordon",
        "uncordon",
        "drain",
        "port-forward",  # Creates a network tunnel
        "proxy",  # Creates proxy to API server
        "debug",  # Debug running pods
        "certificate",  # Certificate management (approve/deny)
    }
)


# Safe subcommands for multi-level commands
SAFE_SUBCOMMANDS = {
    "config": {
        "view",
        "get-contexts",
        "get-clusters",
        "current-context",
        "get-users",
    },
    "auth": {"can-i", "whoami"},
    "rollout": {"status", "history"},
}


# Unsafe subcommands
UNSAFE_SUBCOMMANDS = {
    "config": {
        "set",
        "set-context",
        "set-cluster",
        "set-credentials",
        "delete-context",
        "delete-cluster",
        "delete-user",
        "use-context",
        "use",
        "rename-context",
    },
    "rollout": {"restart", "pause", "resume", "undo"},
}


def classify(tokens: list[str]) -> Classification:
    """Classify kubectl command."""
    base = tokens[0] if tokens else "kubectl"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    # Find the action (skip global flags)
    action = None
    action_idx = 1

    while action_idx < len(tokens):
        token = tokens[action_idx]

        if token.startswith("-"):
            if token in {
                "-n",
                "--namespace",
                "-l",
                "--selector",
                "-o",
                "--output",
                "--context",
                "--cluster",
                "-f",
                "--filename",
            }:
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

    # Check for subcommands first
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

    # Simple safe actions
    if action in SAFE_ACTIONS:
        return Classification("approve", description=desc)

    return Classification("ask", description=desc)
