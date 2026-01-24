"""duckdb handler for Dippy."""

from __future__ import annotations


from dippy.cli import Classification, HandlerContext
from dippy.core.sql import is_readonly_sql

COMMANDS = ["duckdb"]

# DuckDB-specific keywords that perform writes or modifications
_DUCKDB_WRITE = frozenset(
    {"PRAGMA", "ATTACH", "DETACH", "VACUUM", "COPY", "EXPORT", "IMPORT"}
)


def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens

    # Help/version
    if any(t in ("-help", "--help", "-version") for t in tokens):
        return Classification("allow", description="duckdb help/version")

    # Check for -readonly or -safe flags - always safe
    if "-readonly" in tokens or "-safe" in tokens:
        return Classification("allow", description="duckdb (read-only mode)")

    # Check for -init (runs a script file - unknown content)
    if "-init" in tokens:
        return Classification("ask", description="duckdb (init script)")

    # Extract SQL from command line
    # duckdb [OPTIONS] [FILENAME [SQL...]]
    # Also check -c, -s, -cmd options
    sql_parts: list[str] = []
    i = 1
    filename_seen = False
    while i < len(tokens):
        token = tokens[i]
        # Skip option flags that take no argument
        if token in (
            "-ascii",
            "-bail",
            "-batch",
            "-box",
            "-column",
            "-csv",
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
            "-no-stdin",
            "-quote",
            "-readonly",
            "-safe",
            "-stats",
            "-table",
            "-tabs",
            "-unredacted",
            "-unsigned",
            "-version",
        ):
            i += 1
            continue
        # Skip option flags that take one argument
        if token in (
            "-cmd",
            "-init",
            "-separator",
            "-vfs",
            "-storage-version",
            "-newline",
            "-nullvalue",
        ):
            if token == "-cmd" and i + 1 < len(tokens):
                sql_parts.append(tokens[i + 1])
            i += 2
            continue
        # -c and -s run SQL and exit
        if token in ("-c", "-s") and i + 1 < len(tokens):
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
        return Classification("ask", description="duckdb (interactive)")

    # Combine SQL parts
    sql = " ".join(sql_parts)

    # Analyze SQL
    readonly = is_readonly_sql(sql, extra_write=_DUCKDB_WRITE)
    if readonly is True:
        return Classification("allow", description="duckdb (read-only query)")
    if readonly is False:
        return Classification("ask", description="duckdb (write query)")
    # Unknown - ask
    return Classification("ask", description="duckdb (unknown query)")
