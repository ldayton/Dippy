"""
Packer command handler for Dippy.

Packer is a HashiCorp tool for building automated machine images.

Safe operations are read-only inspections and validations.
Unsafe operations include building images (external effects),
installing plugins, and modifying template files.
"""

from dippy.cli import Classification

COMMANDS = ["packer"]

# Safe read-only actions
SAFE_ACTIONS = frozenset(
    {
        "version",
        "validate",  # Check template validity
        "inspect",  # Show template components
        "console",  # Interactive testing (read-only)
    }
)

# Unsafe actions that have external effects or modify files
UNSAFE_ACTIONS = frozenset(
    {
        "build",  # Creates machine images - major external effect
        "init",  # Installs plugins - downloads external content
        "fix",  # Modifies templates
        "hcl2_upgrade",  # Transforms/writes template files
    }
)

# Safe subcommands for plugins
SAFE_PLUGINS_SUBCOMMANDS = frozenset(
    {
        "installed",  # List installed plugins
        "required",  # List required plugins
    }
)

# Unsafe subcommands for plugins
UNSAFE_PLUGINS_SUBCOMMANDS = frozenset(
    {
        "install",  # Installs plugins
        "remove",  # Removes plugins
    }
)


def classify(tokens: list[str]) -> Classification:
    """Classify packer command."""
    base = tokens[0] if tokens else "packer"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    # Check for help flags anywhere
    if "--help" in tokens or "-help" in tokens or "-h" in tokens:
        return Classification("approve", description=f"{base} --help")

    # Check for version flag
    if "--version" in tokens or "-version" in tokens:
        return Classification("approve", description=f"{base} --version")

    # Find action (skip global flags)
    action = None
    action_idx = 1

    while action_idx < len(tokens):
        token = tokens[action_idx]

        if token.startswith("-"):
            action_idx += 1
            continue

        action = token
        break

    if not action:
        return Classification("ask", description=base)

    rest = tokens[action_idx + 1 :] if action_idx + 1 < len(tokens) else []
    desc = f"{base} {action}"

    # Handle plugins subcommand
    if action == "plugins":
        subcommand = _find_subcommand(rest)
        if subcommand:
            desc = f"{desc} {subcommand}"
        if subcommand in SAFE_PLUGINS_SUBCOMMANDS:
            return Classification("approve", description=desc)
        if subcommand in UNSAFE_PLUGINS_SUBCOMMANDS:
            return Classification("ask", description=desc)
        return Classification("ask", description=desc)

    # Handle fmt - safe only with -check, -diff, or -write=false
    if action == "fmt":
        if _is_fmt_safe(rest):
            return Classification("approve", description=desc)
        return Classification("ask", description=desc)

    # Simple safe actions
    if action in SAFE_ACTIONS:
        return Classification("approve", description=desc)

    # Unsafe actions
    if action in UNSAFE_ACTIONS:
        return Classification("ask", description=desc)

    # Unknown actions require confirmation
    return Classification("ask", description=desc)


def _find_subcommand(rest: list[str]) -> str | None:
    """Find the first non-flag token (the subcommand)."""
    for token in rest:
        if not token.startswith("-"):
            return token
    return None


def _is_fmt_safe(rest: list[str]) -> bool:
    """Check if fmt command is safe (read-only mode)."""
    for token in rest:
        if token in {"-check", "-diff"} or token.startswith("-write=false"):
            return True
    return False
