"""mysql handler for Dippy."""

from dippy.cli import Classification, HandlerContext
from dippy.core.sql import is_readonly_sql

COMMANDS = ["mysql"]

# MySQL-specific keywords that perform writes
_MYSQL_WRITE = frozenset({"LOAD"})


def _extract_execute_sql(tokens: list[str]) -> str | None:
    """Extract SQL from -e or --execute option."""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in ("-e", "--execute") and i + 1 < len(tokens):
            return tokens[i + 1]
        if token.startswith("--execute="):
            val = token[len("--execute=") :]
            # Strip surrounding quotes if present
            if len(val) >= 2 and val[0] in ("'", '"') and val[-1] == val[0]:
                val = val[1:-1]
            return val
        if token.startswith("-e") and len(token) > 2:
            # -e'SQL' without space
            return token[2:]
        i += 1
    return None


def classify(ctx: HandlerContext) -> Classification:
    tokens = ctx.tokens

    # Help/version
    if any(t in ("--help", "-?", "--version", "-V") for t in tokens):
        return Classification("allow", description="mysql help/version")

    # Extract SQL from -e/--execute
    sql = _extract_execute_sql(tokens)

    # No SQL found - interactive mode
    if sql is None:
        return Classification("ask", description="mysql (interactive)")

    # Analyze SQL
    readonly = is_readonly_sql(sql, extra_write=_MYSQL_WRITE)
    if readonly is True:
        return Classification("allow", description="mysql (read-only query)")
    if readonly is False:
        return Classification("ask", description="mysql (write query)")
    # Unknown - ask
    return Classification("ask", description="mysql (unknown query)")
