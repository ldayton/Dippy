"""
Auth0 CLI command handler for Dippy.

Auth0 commands for identity management.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["auth0"]

# Safe Auth0 actions (read-only)
SAFE_ACTION_KEYWORDS = frozenset(
    {
        "list",
        "ls",
        "show",
        "get",
        "search",
        "search-by-email",
        "tail",  # logs tail
        "diff",  # actions diff
        "stats",  # event-streams stats
        "--help",
        "-h",  # help flags
    }
)

UNSAFE_ACTION_KEYWORDS = frozenset(
    {
        "create",
        "delete",
        "update",
        "import",
        "export",
        "rm",  # alias for delete
        "add",
        "remove",  # for permissions
        "download",  # quickstarts download
        "use",  # tenants use
        "customize",  # universal-login customize
        "verify",  # domains verify
        "deploy",  # actions deploy
        "enable",
        "disable",  # rules enable/disable
    }
)

# Global flags that take an argument
GLOBAL_FLAGS_WITH_ARG = frozenset(
    {
        "--tenant",
        "-t",
        "--debug",
    }
)


def _check_api(tokens: list[str]) -> bool:
    """Check auth0 api command - approve GET requests only."""
    args = tokens[2:] if len(tokens) > 2 else []
    for arg in args:
        if arg in {"post", "put", "patch", "delete"}:
            return False
        if arg in {"-d", "--data"}:
            return False
    return True


def classify(ctx: HandlerContext) -> Classification:
    """Classify auth0 command."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "auth0"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    parts = _extract_parts(tokens[1:])
    if not parts:
        return Classification("ask", description=base)

    subcommand = parts[0]
    desc = f"{base} {subcommand}"

    if subcommand == "api":
        if _check_api(tokens):
            return Classification("allow", description=desc)
        return Classification("ask", description=desc)

    for part in parts:
        if part in SAFE_ACTION_KEYWORDS:
            return Classification("allow", description=desc)

    for part in parts:
        if part in UNSAFE_ACTION_KEYWORDS:
            return Classification("ask", description=desc)

    return Classification("ask", description=desc)


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
