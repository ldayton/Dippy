"""
UV command handler for Dippy.

UV is a Python package manager with various commands.
Some commands need special handling for inner command checking.
"""

COMMANDS = ["uv", "uvx"]

# Safe uv commands
SAFE_COMMANDS = frozenset(
    {
        "sync",  # Sync dependencies
        "lock",  # Generate lockfile
        "tree",  # Show dependency tree
        "version",
        "help",
        "--version",
        "--help",
        "venv",  # Create virtual environment
        "export",  # Export lockfile to requirements.txt (read-only)
    }
)

# UV pip subcommands that need confirmation
UV_PIP_UNSAFE = frozenset(
    {
        "install",
        "uninstall",
        "sync",
        "compile",
    }
)

# Commands that can execute arbitrary code - always need confirmation in uv run
UV_RUN_UNSAFE_INNER = frozenset(
    {
        "bash",
        "sh",
        "zsh",
        "dash",
        "ksh",
        "fish",  # Shells with -c
        "perl",
        "ruby",
        "node",
        "deno",
        "bun",  # Script interpreters
        "make",
        "cmake",  # Build systems
    }
)

# Commands with subcommands
SAFE_SUBCOMMANDS = {
    "cache": {"dir"},
    "python": {"list", "find", "dir"},
}

# UV pip safe subcommands (handled separately)
UV_PIP_SAFE = frozenset(
    {
        "list",
        "freeze",
        "show",
        "check",
        "tree",
    }
)

UNSAFE_SUBCOMMANDS = {
    "cache": {"clean", "prune"},
    "python": {"install", "uninstall", "pin"},
}

# UV run flags that take an argument
RUN_FLAGS_WITH_ARG = frozenset(
    {
        "--python",
        "-p",
        "--with",
        "--with-requirements",
        "--project",
        "--directory",
        "--group",
        "--extra",
        "--package",
    }
)


def check(tokens: list[str]) -> bool:
    """Check if uv command is safe."""
    if len(tokens) < 2:
        return True  # Just "uv" shows help

    action = tokens[1]

    # Version/help checks
    if action in {"--version", "-v", "--help", "-h", "version", "help"}:
        return True

    # Safe commands
    if action in SAFE_COMMANDS:
        return True

    # Check commands with subcommands
    if action in SAFE_SUBCOMMANDS or action in UNSAFE_SUBCOMMANDS:
        if len(tokens) > 2:
            subcommand = tokens[2]
            if action in SAFE_SUBCOMMANDS and subcommand in SAFE_SUBCOMMANDS[action]:
                return True
            if (
                action in UNSAFE_SUBCOMMANDS
                and subcommand in UNSAFE_SUBCOMMANDS[action]
            ):
                return False
        return action in SAFE_SUBCOMMANDS

    # Handle "uv pip" - check subcommand
    if action == "pip":
        if len(tokens) > 2:
            subcommand = tokens[2]
            if subcommand in UV_PIP_UNSAFE:
                return False
            if subcommand in UV_PIP_SAFE:
                return True
            return False
        return True  # Just "uv pip" shows help

    # Handle "uv run" - need to check the inner command
    if action == "run":
        return _check_uv_run(tokens)

    # Handle "uv tool" - always need confirmation
    if action == "tool":
        return False

    return False


def _check_uv_run(tokens: list[str]) -> bool:
    """Check uv run commands by extracting and checking the inner command."""
    i = 2  # Start after "uv run"
    while i < len(tokens):
        token = tokens[i]

        if token.startswith("-"):
            if token in RUN_FLAGS_WITH_ARG and i + 1 < len(tokens):
                i += 2
            elif "=" in token:
                i += 1
            else:
                i += 1
            continue

        inner_tokens = tokens[i:]
        if not inner_tokens:
            return False

        inner_cmd_name = inner_tokens[0]

        # Block shells and script interpreters
        if inner_cmd_name in UV_RUN_UNSAFE_INNER:
            return False

        # Block python running scripts (but allow python --version)
        if inner_cmd_name in ("python", "python3"):
            if len(inner_tokens) >= 2:
                second = inner_tokens[1]
                if second in ("--version", "-V", "--help", "-h"):
                    return True
            return False

        # Check the inner command using main dippy logic
        inner_cmd = " ".join(inner_tokens)
        from dippy.dippy import check_command, get_current_context

        config, cwd = get_current_context()
        result = check_command(inner_cmd, config, cwd)
        output = result.get("hookSpecificOutput", {})
        return output.get("permissionDecision") == "allow"

    return False
