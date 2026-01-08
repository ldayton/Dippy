"""
Docker command handler for Dippy.

Handles docker, docker-compose, and podman commands.
"""

from typing import Optional


# Safe read-only actions (at the top level)
SAFE_ACTIONS = frozenset({
    "version", "help", "info",
    "ps", "images", "image",
    "inspect", "logs", "stats", "top",
    "port", "diff",
    "history", "search",
    "events", "system",
    "network",  # Some subcommands are safe
    "volume",   # Some subcommands are safe
    "config",   # Some subcommands are safe
    "context",  # Needs subcommand checking
    "export",   # Read-only (exports container to stdout)
    "save",     # Read-only (saves image to stdout)
})


# Unsafe actions
UNSAFE_ACTIONS = frozenset({
    "run", "exec", "start", "stop", "restart",
    "kill", "pause", "unpause",
    "rm", "rmi", "prune",
    "pull", "push",
    "build", "create",
    "commit", "tag",
    "cp", "import", "load",
    "attach",
    "update",
    "compose",  # docker-compose subcommands need checking
    "swarm",  # All swarm operations need confirmation
    "login", "logout",
    "rename", "wait",
})


# Safe subcommands for multi-level commands
SAFE_SUBCOMMANDS = {
    "image": {"ls", "list", "inspect", "history", "save"},
    "container": {"ls", "list", "inspect", "logs", "stats", "top", "port", "diff", "export"},
    "network": {"ls", "list", "inspect"},
    "volume": {"ls", "list", "inspect"},
    "system": {"df", "info", "events"},
    "context": {"ls", "list", "inspect", "show"},
    "config": {"ls", "inspect"},
    "secret": {"ls", "inspect"},
    "service": {"ls", "list", "inspect", "logs", "ps"},
    "stack": {"ls", "ps", "services"},
    "node": {"ls", "inspect", "ps"},
    "compose": {"ps", "logs", "config", "images", "ls", "top", "version", "port", "events"},
    "plugin": {"ls", "list", "inspect"},
    "buildx": {"ls", "inspect", "du", "version"},  # imagetools handled specially
    "manifest": {"inspect"},
    "trust": {"inspect"},
}


# Unsafe subcommands
UNSAFE_SUBCOMMANDS = {
    "image": {"rm", "prune", "build", "push", "pull", "tag", "import", "load"},
    "container": {"rm", "prune", "create", "start", "stop", "restart", "kill", "exec"},
    "network": {"create", "rm", "prune", "connect", "disconnect"},
    "volume": {"create", "rm", "prune"},
    "system": {"prune"},
    "context": {"create", "update", "use", "rm", "import"},
    "compose": {"up", "down", "start", "stop", "restart", "rm", "pull", "build", "exec", "run"},
    "config": {"create", "rm"},
    "secret": {"create", "rm"},
    "service": {"create", "rm", "scale", "update", "rollback"},
    "stack": {"deploy", "rm"},
    "node": {"update", "rm", "promote", "demote"},
    "plugin": {"install", "enable", "disable", "rm", "upgrade", "create", "push"},
    "buildx": {"build", "bake", "create", "rm", "use", "prune"},  # imagetools handled specially
    "manifest": {"create", "push", "annotate", "rm"},
    "trust": {"sign", "revoke"},
    "swarm": {"init", "join", "join-token", "leave", "update", "ca", "unlock", "unlock-key"},
}


# Global flags that take an argument
GLOBAL_FLAGS_WITH_ARG = frozenset({
    "-H", "--host",
    "-c", "--context",
    "-l", "--log-level",
    "--config",
    "--tlscacert", "--tlscert", "--tlskey",
})


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a docker command should be approved or denied.

    Returns:
        (decision, description) where decision is "approve", "deny", or None.
    """
    base = tokens[0]  # "docker", "podman", "docker-compose", etc.

    if len(tokens) < 2:
        return (None, base)

    # Find action (skip global flags)
    action_idx = _find_action_idx(tokens)
    if action_idx >= len(tokens):
        return (None, base)

    action = tokens[action_idx]
    desc = f"{base} {action}"
    rest = tokens[action_idx + 1:] if action_idx + 1 < len(tokens) else []

    # Handle docker-compose / docker compose
    if action == "compose" or tokens[0] in {"docker-compose", "podman-compose"}:
        return _check_compose(tokens, action_idx, base)

    # Check subcommands for multi-level commands
    if action in SAFE_SUBCOMMANDS or action in UNSAFE_SUBCOMMANDS:
        subcommand = _find_subcommand(rest)
        if subcommand:
            # Handle nested subcommands (e.g., buildx imagetools inspect)
            if action == "buildx" and subcommand == "imagetools":
                # Find the imagetools action
                sub_rest = rest[rest.index(subcommand) + 1:] if subcommand in rest else []
                imagetools_action = _find_subcommand(sub_rest)
                if imagetools_action == "inspect":
                    return ("approve", desc)
                if imagetools_action == "create":
                    return (None, desc)
                return (None, desc)  # Unknown imagetools action

            if subcommand in SAFE_SUBCOMMANDS.get(action, set()):
                # Special case: image save -o writes to file
                if action == "image" and subcommand == "save" and _has_output_flag(rest):
                    return (None, desc)
                return ("approve", desc)
            if subcommand in UNSAFE_SUBCOMMANDS.get(action, set()):
                return (None, desc)

    # Simple safe actions
    if action in SAFE_ACTIONS:
        # export/save without -o writes to stdout (safe)
        if action in {"export", "save"} and _has_output_flag(rest):
            return (None, desc)
        return ("approve", desc)

    # Unsafe actions need confirmation
    if action in UNSAFE_ACTIONS:
        return (None, desc)

    return (None, desc)


def _find_action_idx(tokens: list[str]) -> int:
    """Find the index of the docker action, skipping global flags."""
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            if token in GLOBAL_FLAGS_WITH_ARG and i + 1 < len(tokens):
                i += 2  # Skip flag and its argument
            elif "=" in token:
                i += 1  # Flag with value
            else:
                i += 1  # Boolean flag
            continue
        return i
    return len(tokens)


def _find_subcommand(rest: list[str]) -> Optional[str]:
    """Find the first non-flag token (the subcommand)."""
    for token in rest:
        if not token.startswith("-"):
            return token
    return None


def _has_output_flag(tokens: list[str]) -> bool:
    """Check if -o or --output flag is present."""
    for i, token in enumerate(tokens):
        if token in {"-o", "--output"}:
            return True
        if token.startswith("-o") or token.startswith("--output="):
            return True
    return False


def _check_compose(tokens: list[str], start_idx: int, base: str) -> tuple[Optional[str], str]:
    """Check docker-compose commands."""
    # Compose flags that take arguments
    compose_flags_with_arg = {
        "-f", "--file",
        "-p", "--project-name",
        "--project-directory",
        "--env-file",
        "--profile",
        "--ansi",
    }

    # Determine starting position based on command type
    # For "docker compose ...", start after "compose"
    # For "docker-compose ..." or "podman-compose ...", start after the command itself
    if tokens[0] in {"docker-compose", "podman-compose"}:
        i = 1  # Start after the command
        compose_base = tokens[0]
    elif start_idx < len(tokens) and tokens[start_idx] == "compose":
        i = start_idx + 1  # Start after "compose"
        compose_base = f"{base} compose"
    else:
        i = start_idx
        compose_base = base

    # Find compose action, skipping compose-specific flags
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            if token in compose_flags_with_arg and i + 1 < len(tokens):
                i += 2
            elif "=" in token:
                i += 1
            else:
                i += 1
            continue

        # Found the compose action
        desc = f"{compose_base} {token}"
        if token in {"ps", "logs", "config", "images", "ls", "top", "version", "port", "events"}:
            return ("approve", desc)
        if token in {"up", "down", "start", "stop", "restart", "rm", "pull", "build", "exec", "run", "create"}:
            return (None, desc)
        return (None, desc)

    return (None, compose_base)
