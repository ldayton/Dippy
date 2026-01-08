"""
Auth0 CLI command handler for Dippy.

Auth0 commands for identity management.
"""

from typing import Optional


# Safe Auth0 actions (read-only)
SAFE_ACTION_KEYWORDS = frozenset({
    "list", "ls", "show", "get",
    "search", "search-by-email",
    "tail",  # logs tail
    "diff",  # actions diff
    "stats",  # event-streams stats
    "--help", "-h",  # help flags
})

UNSAFE_ACTION_KEYWORDS = frozenset({
    "create", "delete", "update",
    "import", "export",
    "rm",  # alias for delete
    "add", "remove",  # for permissions
    "download",  # quickstarts download
    "use",  # tenants use
    "customize",  # universal-login customize
    "verify",  # domains verify
    "deploy",  # actions deploy
    "enable", "disable",  # rules enable/disable
})

# Global flags that take an argument
GLOBAL_FLAGS_WITH_ARG = frozenset({
    "--tenant", "-t",
    "--debug",
})


def _check_api(tokens: list[str]) -> Optional[str]:
    """Check auth0 api command - approve GET requests only."""
    # tokens: ['auth0', 'api', 'get', 'path'] or ['auth0', 'api', 'path'] (defaults to GET)
    args = tokens[2:] if len(tokens) > 2 else []
    for arg in args:
        if arg in {"post", "put", "patch", "delete"}:
            return None
        if arg in {"-d", "--data"}:
            return None
    return "approve"


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if an auth0 command should be approved.

    Returns:
        "approve" - Safe read-only operation
        None - Needs user confirmation
    """
    if len(tokens) < 2:
        return (None, "auth0")

    # Extract parts, skipping global flags
    parts = _extract_parts(tokens[1:])

    if not parts:
        return (None, "auth0")

    subcommand = parts[0]

    # Special handling for api command
    if subcommand == "api":
        result = _check_api(tokens)
        return (result, "auth0 api") if result else (None, "auth0 api")

    # Check all parts for safe/unsafe action keywords
    for part in parts:
        if part in SAFE_ACTION_KEYWORDS:
            return ("approve", "auth0")

    for part in parts:
        if part in UNSAFE_ACTION_KEYWORDS:
            return (None, "auth0")

    # Unknown - ask user
    return (None, "auth0")


def _extract_parts(tokens: list[str]) -> list[str]:
    """Extract command parts, keeping help flags but skipping other flags."""
    parts = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            # Keep help flags as they affect safety decision
            if token in {"--help", "-h"}:
                parts.append(token)
            elif token in GLOBAL_FLAGS_WITH_ARG and i + 1 < len(tokens):
                i += 2
                continue
            i += 1
            continue
        parts.append(token)
        i += 1
    return parts
