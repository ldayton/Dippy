"""
Auth0 CLI command handler for Dippy.

Auth0 commands for identity management.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

# Safe Auth0 actions (read-only)
SAFE_ACTION_KEYWORDS = frozenset({
    "list", "show", "get",
    "search", "search-by-email",
    "tail",  # logs tail
    "diff",  # actions diff
    "stats",  # event-streams stats
})

UNSAFE_ACTION_KEYWORDS = frozenset({
    "create", "delete", "update",
    "import", "export",
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


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if an auth0 command should be approved.

    Returns:
        "approve" - Safe read-only operation
        None - Needs user confirmation
    """
    if len(tokens) < 2:
        return None

    # Extract parts, skipping global flags
    parts = _extract_parts(tokens[1:])

    if not parts:
        return None

    subcommand = parts[0]

    # Special handling for api command
    if subcommand == "api":
        return _check_api(tokens)

    # Check all parts for safe/unsafe action keywords
    for part in parts:
        if part in SAFE_ACTION_KEYWORDS:
            return "approve"

    for part in parts:
        if part in UNSAFE_ACTION_KEYWORDS:
            return None

    # Unknown - ask user
    return None


def _extract_parts(tokens: list[str]) -> list[str]:
    """Extract command parts, skipping global flags."""
    parts = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            if token in GLOBAL_FLAGS_WITH_ARG and i + 1 < len(tokens):
                i += 2
            else:
                i += 1
            continue
        parts.append(token)
        i += 1
    return parts
