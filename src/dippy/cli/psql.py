"""psql handler for Dippy."""

from dippy.cli import Classification, HandlerContext
from dippy.core.sql import is_readonly_sql

COMMANDS = ["psql"]

# PostgreSQL-specific keywords that perform writes or modifications
_POSTGRES_WRITE = frozenset({"COPY", "VACUUM", "CLUSTER", "REINDEX", "ANALYZE"})


def _extract_command_sql(tokens: list[str]) -> list[str]:
    """Extract SQL from -c or --command options. Returns list of SQL strings."""
    sql_list: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in ("-c", "--command") and i + 1 < len(tokens):
            sql_list.append(tokens[i + 1])
            i += 2
            continue
        if token.startswith("--command="):
            val = token[len("--command=") :]
            # Strip surrounding quotes if present
            if len(val) >= 2 and val[0] in ("'", '"') and val[-1] == val[0]:
                val = val[1:-1]
            sql_list.append(val)
            i += 1
            continue
        i += 1
    return sql_list


def _has_file_option(tokens: list[str]) -> bool:
    """Check if -f or --file option is present."""
    for i, token in enumerate(tokens):
        if token in ("-f", "--file"):
            return True
        if token.startswith("--file=") or token.startswith("-f"):
            return True
    return False


def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens

    # Help/version
    if "--help" in tokens or "--version" in tokens or "-V" in tokens:
        return Classification("allow", description="psql help/version")

    # List databases is read-only
    if "-l" in tokens or "--list" in tokens:
        return Classification("allow", description="psql --list")

    # File input - unknown content
    if _has_file_option(tokens):
        return Classification("ask", description="psql (file input)")

    # Extract SQL from -c/--command options
    sql_list = _extract_command_sql(tokens)

    # No SQL found - interactive mode
    if not sql_list:
        return Classification("ask", description="psql (interactive)")

    # Analyze all SQL commands - all must be read-only
    for sql in sql_list:
        readonly = is_readonly_sql(sql, extra_write=_POSTGRES_WRITE)
        if readonly is False:
            return Classification("ask", description="psql (write query)")
        if readonly is None:
            return Classification("ask", description="psql (unknown query)")

    # All commands are read-only
    return Classification("allow", description="psql (read-only query)")
