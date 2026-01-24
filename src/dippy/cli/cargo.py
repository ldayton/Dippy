"""
Cargo (Rust) CLI handler for Dippy.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["cargo"]

SAFE_ACTIONS = frozenset(
    {
        "help",
        "-h",
        "--help",
        "version",
        "-V",
        "--version",
        "search",
        "info",
        "tree",
        "metadata",
        "read-manifest",
        "locate-project",
        "pkgid",
        "verify-project",
        "check",
        "c",  # Type checking only
        "clippy",  # Linting only
        "fmt",  # Formatting
        "doc",  # Generate docs
        "fetch",  # Download deps
        "generate-lockfile",
        "update",  # Update lockfile
        "vendor",
        "login",
        "logout",
        "owner",
    }
)

# Short aliases that need expansion for clarity
ACTION_ALIASES = {
    "r": "run",
    "b": "build",
    "t": "test",
}


def classify(ctx: HandlerContext) -> Classification:
    """Classify cargo command."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "cargo"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    action = tokens[1]

    if action in SAFE_ACTIONS:
        return Classification("allow", description=f"{base} {action}")

    # Expand short aliases for clarity
    display_action = ACTION_ALIASES.get(action, action)
    return Classification("ask", description=f"{base} {display_action}")
