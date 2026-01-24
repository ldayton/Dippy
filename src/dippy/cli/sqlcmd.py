"""sqlcmd (go-sqlcmd) handler for Dippy."""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext
from dippy.core.sql import is_readonly_sql

COMMANDS = ["sqlcmd"]

# Safe subcommands that don't modify anything
_SAFE_SUBCOMMANDS = frozenset({"config", "open", "help", "completion"})

# Unsafe subcommands that modify state
_UNSAFE_SUBCOMMANDS = frozenset({"create", "install", "delete", "start", "stop"})


def _extract_query_sql(tokens: list[str]) -> str | None:
    """Extract SQL from query subcommand."""
    # Find 'query' subcommand
    try:
        query_idx = tokens.index("query")
    except ValueError:
        return None

    # Look for SQL after 'query'
    i = query_idx + 1
    while i < len(tokens):
        token = tokens[i]
        # Check for flag options
        if token in ("-q", "--query", "-t", "--text") and i + 1 < len(tokens):
            return tokens[i + 1]
        if token in ("-d", "--database", "-h", "--help"):
            i += 2 if token in ("-d", "--database") else 1
            continue
        if token.startswith("-"):
            i += 1
            continue
        # This should be the SQL text (positional argument)
        return token
    return None


def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens

    # Help/version at top level
    if any(t in ("--help", "-h", "--version") for t in tokens):
        return Classification("allow", description="sqlcmd help/version")

    # Get subcommand (first non-flag argument after 'sqlcmd')
    subcommand = None
    for token in tokens[1:]:
        if not token.startswith("-"):
            subcommand = token
            break

    if subcommand is None:
        return Classification("ask", description="sqlcmd (no subcommand)")

    # Safe subcommands
    if subcommand in _SAFE_SUBCOMMANDS:
        return Classification("allow", description=f"sqlcmd {subcommand}")

    # Unsafe subcommands
    if subcommand in _UNSAFE_SUBCOMMANDS:
        return Classification("ask", description=f"sqlcmd {subcommand}")

    # Query subcommand - analyze SQL
    if subcommand == "query":
        sql = _extract_query_sql(tokens)
        if sql is None:
            return Classification("ask", description="sqlcmd query (no SQL)")

        readonly = is_readonly_sql(sql)
        if readonly is True:
            return Classification("allow", description="sqlcmd query (read-only)")
        if readonly is False:
            return Classification("ask", description="sqlcmd query (write)")
        return Classification("ask", description="sqlcmd query (unknown)")

    # Unknown subcommand
    return Classification("ask", description=f"sqlcmd {subcommand}")
