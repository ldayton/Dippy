"""
UV command handler for Dippy.

UV is a Python package manager with various commands.
Some commands need special handling for inner command checking.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

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
})

# UV pip subcommands that need confirmation
UV_PIP_UNSAFE = frozenset({
    "install", "uninstall", "sync",
})

# Commands that need inner command checking
RUN_COMMANDS = frozenset({
    "run",
    "tool",
})

# UV run flags that take an argument
RUN_FLAGS_WITH_ARG = frozenset({
    "--python", "-p",
    "--with", "--with-requirements",
    "--project", "--directory",
    "--group", "--extra",
    "--package",
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """Check if a uv command should be approved."""
    if len(tokens) < 2:
        return "approve"  # Just "uv" shows help

    action = tokens[1]

    # Version/help checks
    if action in {"--version", "-v", "--help", "-h", "version", "help"}:
        return "approve"

    # Safe commands
    if action in SAFE_COMMANDS:
        return "approve"

    # Handle "uv pip" - check subcommand
    if action == "pip":
        if len(tokens) > 2:
            subcommand = tokens[2]
            if subcommand in UV_PIP_UNSAFE:
                return None  # install/uninstall need confirmation
            # list, show, etc. are safe
            return "approve"
        return "approve"  # Just "uv pip" shows help

    # Handle "uv run" - need to check the inner command
    if action in RUN_COMMANDS:
        return _check_uv_run(tokens)

    # Unknown - ask user
    return None


def _check_uv_run(tokens: list[str]) -> Optional[str]:
    """Check uv run commands by extracting and checking the inner command."""
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
            return None

        # Check the inner command using main dippy logic
        inner_cmd = " ".join(inner_tokens)
        from dippy.dippy import check_command
        result = check_command(inner_cmd)
        return "approve" if result.get("decision") == "approve" else None

    return None
