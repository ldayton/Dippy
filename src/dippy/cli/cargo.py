"""
Cargo (Rust) CLI handler for Dippy.
"""

from typing import Optional


SAFE_ACTIONS = frozenset({
    "help", "-h", "--help",
    "version", "-V", "--version",
    "search", "info",
    "tree", "metadata",
    "read-manifest", "locate-project",
    "pkgid", "verify-project",
    "check", "c",  # Type checking only
    "clippy",  # Linting only
    "fmt",  # Formatting
    "doc",  # Generate docs
    "fetch",  # Download deps
    "generate-lockfile",
    "update",  # Update lockfile
    "vendor",
    "login", "logout", "owner",
})


UNSAFE_ACTIONS = frozenset({
    "build", "b",
    "run", "r",
    "test", "t",
    "bench",
    "install", "uninstall",
    "publish", "yank",
    "clean",
    "new", "init",
    "add", "remove", "rm",
    "fix",
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """Check if a cargo command should be approved or denied."""
    if len(tokens) < 2:
        return None
    
    action = tokens[1]
    
    if action in SAFE_ACTIONS:
        return "approve"
    
    if action in UNSAFE_ACTIONS:
        return None
    
    return None
