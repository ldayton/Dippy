"""
UV command handler for Dippy.

UV is a Python package manager with various commands.
Some commands need special handling for inner command checking.
"""

from typing import Optional


# Safe uv commands
SAFE_COMMANDS = frozenset({
    "sync",     # Sync dependencies
    "lock",     # Generate lockfile
    "tree",     # Show dependency tree
    "version",
    "help",
    "--version",
    "--help",
    "venv",     # Create virtual environment
    "export",   # Export lockfile to requirements.txt (read-only)
})

# UV pip subcommands that need confirmation
UV_PIP_UNSAFE = frozenset({
    "install", "uninstall", "sync", "compile",
})

# Commands that can execute arbitrary code - always need confirmation in uv run
UV_RUN_UNSAFE_INNER = frozenset({
    "bash", "sh", "zsh", "dash", "ksh", "fish",  # Shells with -c
    "perl", "ruby", "node", "deno", "bun",  # Script interpreters
    "make", "cmake",  # Build systems
})

# Commands with subcommands
SAFE_SUBCOMMANDS = {
    "cache": {"dir"},
    "python": {"list", "find", "dir"},
}

# UV pip safe subcommands (handled separately)
UV_PIP_SAFE = frozenset({
    "list", "freeze", "show", "check", "tree",
})

UNSAFE_SUBCOMMANDS = {
    "cache": {"clean", "prune"},
    "python": {"install", "uninstall", "pin"},
}

# UV run flags that take an argument
RUN_FLAGS_WITH_ARG = frozenset({
    "--python", "-p",
    "--with", "--with-requirements",
    "--project", "--directory",
    "--group", "--extra",
    "--package",
})


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """Check if a uv command should be approved."""
    if len(tokens) < 2:
        return ("approve", "uv")  # Just "uv" shows help

    action = tokens[1]

    # Version/help checks
    if action in {"--version", "-v", "--help", "-h", "version", "help"}:
        return ("approve", "uv")

    # Safe commands
    if action in SAFE_COMMANDS:
        return ("approve", "uv")

    # Check commands with subcommands
    if action in SAFE_SUBCOMMANDS or action in UNSAFE_SUBCOMMANDS:
        if len(tokens) > 2:
            subcommand = tokens[2]
            # Check safe subcommands first
            if action in SAFE_SUBCOMMANDS and subcommand in SAFE_SUBCOMMANDS[action]:
                return ("approve", "uv")
            # Then unsafe subcommands
            if action in UNSAFE_SUBCOMMANDS and subcommand in UNSAFE_SUBCOMMANDS[action]:
                return (None, "uv")
        # Just "uv cache" or "uv python" alone - show help
        return ("approve", "uv") if action in SAFE_SUBCOMMANDS else (None, "uv")

    # Handle "uv pip" - check subcommand
    if action == "pip":
        if len(tokens) > 2:
            subcommand = tokens[2]
            if subcommand in UV_PIP_UNSAFE:
                return (None, "uv")  # install/uninstall need confirmation
            if subcommand in UV_PIP_SAFE:
                return ("approve", "uv")
            return (None, "uv")  # Unknown pip subcommand
        return ("approve", "uv")  # Just "uv pip" shows help

    # Handle "uv run" - need to check the inner command
    if action == "run":
        return _check_uv_run(tokens)

    # Handle "uv tool" - only "tool run" checks inner command, others are unsafe
    if action == "tool":
        if len(tokens) > 2:
            tool_subcmd = tokens[2]
            if tool_subcmd == "run":
                # uv tool run <tool> - check the inner tool
                return _check_uv_tool_run(tokens)
        # All other tool subcommands (install, uninstall, list, dir, etc.) need confirmation
        return (None, "uv")

    # Unknown - ask user
    return (None, "uv")


def _check_uv_run(tokens: list[str]) -> tuple[Optional[str], str]:
    """Check uv run commands by extracting and checking the inner command.

    Uses main dippy logic for the inner command, but blocks shells and
    script interpreters that can execute arbitrary code.
    """
    # Find where the inner command starts (after uv run and its flags)
    i = 2  # Start after "uv run"
    while i < len(tokens):
        token = tokens[i]

        # Skip uv run flags
        if token.startswith("-"):
            if token in RUN_FLAGS_WITH_ARG and i + 1 < len(tokens):
                i += 2  # Skip flag and its argument
            elif "=" in token:
                i += 1  # Flag with value
            else:
                i += 1  # Boolean flag
            continue

        # Found the inner command
        inner_tokens = tokens[i:]
        if not inner_tokens:
            return (None, "uv")

        inner_cmd_name = inner_tokens[0]

        # Block shells and script interpreters - can execute arbitrary code
        if inner_cmd_name in UV_RUN_UNSAFE_INNER:
            return (None, "uv")

        # Block python running scripts (but allow python --version)
        if inner_cmd_name in ("python", "python3"):
            if len(inner_tokens) >= 2:
                second = inner_tokens[1]
                # Allow version/help checks
                if second in ("--version", "-V", "--help", "-h"):
                    return ("approve", "uv")
            # Running scripts or python -c needs confirmation
            return (None, "uv")

        # Check the inner command using main dippy logic
        inner_cmd = " ".join(inner_tokens)
        from dippy.dippy import check_command
        result = check_command(inner_cmd)
        output = result.get("hookSpecificOutput", {})
        decision = output.get("permissionDecision")
        inner_reason = output.get("permissionDecisionReason", "").removeprefix("🐤 ")
        desc = f"uv run {inner_reason}" if inner_reason else "uv run"
        return ("approve", desc) if decision == "allow" else (None, desc)

    return (None, "uv")


def _check_uv_tool_run(tokens: list[str]) -> tuple[Optional[str], str]:
    """Check uv tool run commands - always need confirmation.

    uv tool run executes arbitrary tools, so always require confirmation.
    """
    # uv tool run always needs confirmation - it runs arbitrary code
    return (None, "uv")
