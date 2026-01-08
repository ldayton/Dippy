"""
Cargo (Rust) CLI handler for Dippy.
"""


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


def check(tokens: list[str]) -> bool:
    """Check if cargo command is safe."""
    if len(tokens) < 2:
        return False

    action = tokens[1]
    return action in SAFE_ACTIONS
