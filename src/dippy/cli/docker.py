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
    "service": {"ls", "inspect", "logs", "ps"},
    "stack": {"ls", "ps", "services"},
    "node": {"ls", "inspect", "ps"},
    "compose": {"ps", "logs", "config", "images", "ls", "top", "version", "port", "events"},
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
}


# Global flags that take an argument
GLOBAL_FLAGS_WITH_ARG = frozenset({
    "-H", "--host",
    "-c", "--context",
    "-l", "--log-level",
    "--config",
    "--tlscacert", "--tlscert", "--tlskey",
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if a docker command should be approved or denied.
    """
    if len(tokens) < 2:
        return None

    # Find action (skip global flags)
    action_idx = _find_action_idx(tokens)
    if action_idx >= len(tokens):
        return None

    action = tokens[action_idx]
    rest = tokens[action_idx + 1:] if action_idx + 1 < len(tokens) else []

    # Handle docker-compose / docker compose
    if action == "compose" or tokens[0] in {"docker-compose", "podman-compose"}:
        return _check_compose(tokens, action_idx)

    # Check subcommands for multi-level commands
    if action in SAFE_SUBCOMMANDS:
        subcommand = _find_subcommand(rest)
        if subcommand:
            if subcommand in SAFE_SUBCOMMANDS.get(action, set()):
                # Special case: image save -o writes to file
                if action == "image" and subcommand == "save" and _has_output_flag(rest):
                    return None
                return "approve"
            if subcommand in UNSAFE_SUBCOMMANDS.get(action, set()):
                return None

    # Simple safe actions
    if action in SAFE_ACTIONS:
        # export/save without -o writes to stdout (safe)
        if action in {"export", "save"} and _has_output_flag(rest):
            return None
        return "approve"

    # Unsafe actions need confirmation
    if action in UNSAFE_ACTIONS:
        return None

    return None


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


def _check_compose(tokens: list[str], start_idx: int) -> Optional[str]:
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

    # Find compose action, skipping compose-specific flags
    i = start_idx + 1 if start_idx < len(tokens) and tokens[start_idx] == "compose" else start_idx
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
        if token in {"ps", "logs", "config", "images", "ls", "top", "version", "port", "events"}:
            return "approve"
        if token in {"up", "down", "start", "stop", "restart", "rm", "pull", "build", "exec", "run", "create"}:
            return None
        break

    return None
