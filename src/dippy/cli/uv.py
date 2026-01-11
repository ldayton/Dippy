"""
UV command handler for Dippy.

UV is a Python package manager with various commands.
Some commands need special handling for inner command checking.
"""

from dippy.cli import Classification

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


def classify(tokens: list[str]) -> Classification:
    """Classify uv command."""
    if len(tokens) < 2:
        return Classification("approve")  # Just "uv" shows help

    action = tokens[1]

    # Version/help checks
    if action in {"--version", "-v", "--help", "-h", "version", "help"}:
        return Classification("approve", description=f"uv {action}")

    # Safe commands
    if action in SAFE_COMMANDS:
        return Classification("approve", description=f"uv {action}")

    # Check commands with subcommands
    if action in SAFE_SUBCOMMANDS or action in UNSAFE_SUBCOMMANDS:
        if len(tokens) > 2:
            subcommand = tokens[2]
            if action in SAFE_SUBCOMMANDS and subcommand in SAFE_SUBCOMMANDS[action]:
                return Classification(
                    "approve", description=f"uv {action} {subcommand}"
                )
            if (
                action in UNSAFE_SUBCOMMANDS
                and subcommand in UNSAFE_SUBCOMMANDS[action]
            ):
                return Classification("ask", description=f"uv {action} {subcommand}")
        if action in SAFE_SUBCOMMANDS:
            return Classification("approve", description=f"uv {action}")
        return Classification("ask", description=f"uv {action}")

    # Handle "uv pip" - check subcommand
    if action == "pip":
        if len(tokens) > 2:
            subcommand = tokens[2]
            if subcommand in UV_PIP_UNSAFE:
                return Classification("ask", description=f"uv pip {subcommand}")
            if subcommand in UV_PIP_SAFE:
                return Classification("approve", description=f"uv pip {subcommand}")
            return Classification("ask", description=f"uv pip {subcommand}")
        return Classification(
            "approve", description="uv pip"
        )  # Just "uv pip" shows help

    # Handle "uv run" - need to check the inner command
    if action == "run":
        return _classify_uv_run(tokens)

    # Handle "uv tool" - always need confirmation
    if action == "tool":
        subcommand = tokens[2] if len(tokens) > 2 else ""
        return Classification("ask", description=f"uv tool {subcommand}".strip())

    return Classification("ask", description=f"uv {action}")


def _classify_uv_run(tokens: list[str]) -> Classification:
    """Classify uv run commands by extracting and checking the inner command."""
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
            return Classification("ask", description="uv run")

        inner_cmd_name = inner_tokens[0]

        # Block shells and script interpreters
        if inner_cmd_name in UV_RUN_UNSAFE_INNER:
            return Classification("ask", description=f"uv run {inner_cmd_name}")

        # Block python running scripts (but allow python --version)
        if inner_cmd_name in ("python", "python3"):
            if len(inner_tokens) >= 2:
                second = inner_tokens[1]
                if second in ("--version", "-V", "--help", "-h"):
                    return Classification(
                        "approve", description=f"uv run {inner_cmd_name} {second}"
                    )
            return Classification("ask", description=f"uv run {inner_cmd_name}")

        # Delegate to inner command check
        inner_cmd = " ".join(inner_tokens)
        return Classification(
            "delegate", inner_command=inner_cmd, description=f"uv run {inner_cmd_name}"
        )

    return Classification("ask", description="uv run")
