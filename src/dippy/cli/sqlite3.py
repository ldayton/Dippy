"""sqlite3 handler for Dippy."""

from __future__ import annotations


from dippy.cli import Classification, HandlerContext
from dippy.core.sql import is_readonly_sql

COMMANDS = ["sqlite3"]

# SQLite-specific keywords that perform writes or modifications
_SQLITE_WRITE = frozenset(
    {"PRAGMA", "ATTACH", "DETACH", "VACUUM", "REINDEX", "ANALYZE"}
)


def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens
    # Help/version
    if any(t in ("-help", "--help", "-version") for t in tokens):
        return Classification("allow", description="sqlite3 help/version")

    # Check for -readonly or -safe flags - always safe
    if "-readonly" in tokens or "-safe" in tokens:
        return Classification("allow", description="sqlite3 (read-only mode)")

    # Check for -init (runs a script file - unknown content)
    if "-init" in tokens:
        return Classification("ask", description="sqlite3 (init script)")

    # Extract SQL from command line
    # sqlite3 [OPTIONS] [FILENAME [SQL...]]
    # Also check -cmd COMMAND
    sql_parts: list[str] = []
    i = 1
    filename_seen = False
    while i < len(tokens):
        token = tokens[i]
        # Skip option flags that take no argument
        if token in (
            "-append",
            "-ascii",
            "-bail",
            "-batch",
            "-box",
            "-column",
            "-csv",
            "-deserialize",
            "-echo",
            "-header",
            "-noheader",
            "-help",
            "-html",
            "-interactive",
            "-json",
            "-line",
            "-list",
            "-markdown",
            "-memtrace",
            "-nofollow",
            "-quote",
            "-readonly",
            "-safe",
            "-stats",
            "-table",
            "-tabs",
            "-version",
            "-vfstrace",
        ):
            i += 1
            continue
        # Skip option flags that take one argument
        if token in (
            "-cmd",
            "-init",
            "-key",
            "-hexkey",
            "-textkey",
            "-lookaside",
            "-maxsize",
            "-newline",
            "-nonce",
            "-nullvalue",
            "-pagecache",
            "-separator",
            "-vfs",
            "-escape",
            "-A",
        ):
            if token == "-cmd" and i + 1 < len(tokens):
                sql_parts.append(tokens[i + 1])
            i += 2
            continue
        # This should be either filename or SQL
        if token.startswith("-"):
            # Unknown option
            i += 1
            continue
        if not filename_seen:
            # First non-option is filename (could be :memory: or a path)
            filename_seen = True
            i += 1
            continue
        # Everything after filename is SQL
        sql_parts.append(token)
        i += 1

    # No SQL found - interactive mode
    if not sql_parts:
        return Classification("ask", description="sqlite3 (interactive)")

    # Combine SQL parts (multiple arguments are separate statements)
    sql = " ".join(sql_parts)

    # Analyze SQL
    readonly = is_readonly_sql(sql, extra_write=_SQLITE_WRITE)
    if readonly is True:
        return Classification("allow", description="sqlite3 (read-only query)")
    if readonly is False:
        return Classification("ask", description="sqlite3 (write query)")
    # Unknown - ask
    return Classification("ask", description="sqlite3 (unknown query)")
