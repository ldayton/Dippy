"""
Homebrew CLI handler for Dippy.
"""

COMMANDS = ["brew"]

# Actions that only read data
SAFE_ACTIONS = frozenset({
    # Info and listing
    "list", "ls", "leaves",
    "info", "desc", "home", "homepage",
    "deps", "uses", "options",
    "search", "doctor", "config",
    "outdated",

    # Aliases
    "dr",  # doctor alias
    "-S",  # search alias

    # Additional info commands
    "missing",
    "tap-info",
    "formulae", "casks",
    "log", "cat", "commands",
    "fetch",  # Just downloads, doesn't install
    "docs", "shellenv",
    # Note: analytics handled specially (on/off modify settings)

    # Help and version
    "--version", "-v", "help",  # -v is version for brew specifically
})


# Global flags that act like read-only commands
SAFE_GLOBAL_FLAGS = frozenset({
    "--cache",
    "--cellar",
    "--caskroom",
    "--prefix",
    "--repository", "--repo",
    "--env",
    "--taps",
    "--config",  # Same as config command
})


# Actions that modify state
UNSAFE_ACTIONS = frozenset({
    "install", "uninstall", "remove", "rm",
    "upgrade", "update",
    "link", "unlink",
    "cleanup", "autoremove",
    "tap", "untap",
    "pin", "unpin",  # These modify pinning state
    "cask",  # Needs subcommand checking
    "services",  # Needs subcommand checking
    "bundle",  # Needs subcommand checking
})


# Safe subcommands for multi-level commands
SAFE_SUBCOMMANDS = {
    "cask": {"list", "info", "search", "outdated", "home"},
    "bundle": {"check", "list"},  # These are read-only
}


# Unsafe subcommands that require confirmation
UNSAFE_SUBCOMMANDS = {
    "cask": {"install", "uninstall", "upgrade", "zap"},
    "services": {"start", "stop", "restart", "run", "cleanup"},
    "bundle": {"install", "dump", "cleanup", "exec"},
}


def check(tokens: list[str]) -> bool:
    """Check if brew command is safe."""
    if len(tokens) < 2:
        return False

    action = tokens[1]
    rest = tokens[2:] if len(tokens) > 2 else []

    # Check global flags that act like commands
    if action in SAFE_GLOBAL_FLAGS:
        return True

    # Check subcommands for multi-level commands
    if action in SAFE_SUBCOMMANDS and rest:
        subcommand = _find_subcommand(rest)
        if subcommand in SAFE_SUBCOMMANDS[action]:
            return True

    if action in UNSAFE_SUBCOMMANDS and rest:
        subcommand = _find_subcommand(rest)
        if subcommand in UNSAFE_SUBCOMMANDS[action]:
            return False
        if action == "services":
            return False

    if action == "services":
        return False

    if action == "bundle":
        return False

    # analytics: 'state' is safe, 'on'/'off' modify settings
    if action == "analytics":
        if rest:
            subcommand = _find_subcommand(rest)
            if subcommand in {"on", "off"}:
                return False
        return True

    if action in SAFE_ACTIONS:
        return True

    return False


def _find_subcommand(rest: list[str]) -> str | None:
    """Find the first non-flag token (the subcommand)."""
    for token in rest:
        if not token.startswith("-"):
            return token
    return None
