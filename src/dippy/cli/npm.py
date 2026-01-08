"""
Node package manager CLI handler for Dippy.

Handles npm, yarn, and pnpm commands.
"""

from typing import Optional


SAFE_ACTIONS = frozenset({
    "list", "ls", "ll", "la",
    "info", "show", "view", "v",
    "search", "find",
    "outdated", "audit",
    "help", "version", "-v", "--version",
    "config", "get",
    "root", "prefix", "bin",
    "docs", "home", "bugs", "repo",
    "owner", "whoami", "ping",
    "explain", "why",
    "pack",  # Creates tarball but doesn't publish
    "fund",
    "doctor",  # Health check
    "licenses",  # yarn/pnpm licenses list
})


UNSAFE_ACTIONS = frozenset({
    "install", "i", "add",
    "uninstall", "remove", "rm", "un",
    "update", "upgrade", "up",
    "run", "exec", "x",
    "start", "stop", "restart", "test", "t",
    "publish", "unpublish",
    "link", "unlink",
    "prune", "dedupe",
    "rebuild", "build",
    "init", "create",
    "cache",  # cache clean is destructive
    "set",
})


SAFE_SUBCOMMANDS = {
    "config": {"list", "get"},
    "cache": {"ls", "list"},
    "run": {"--list"},
}


def check(command: str, tokens: list[str]) -> Optional[str]:
    """Check if an npm/yarn/pnpm command should be approved or denied."""
    if len(tokens) < 2:
        return None
    
    action = tokens[1]
    rest = tokens[2:] if len(tokens) > 2 else []
    
    # Check subcommands
    if action in SAFE_SUBCOMMANDS and rest:
        for token in rest:
            if token in SAFE_SUBCOMMANDS[action]:
                return "approve"
    
    if action in SAFE_ACTIONS:
        return "approve"
    
    if action in UNSAFE_ACTIONS:
        # Special case: npm run --list is safe
        if action == "run" and "--list" in rest:
            return "approve"
        return None
    
    return None
