"""SQL statement classification for Dippy.

Provides dialect-agnostic detection of read-only vs write SQL statements.
"""

from __future__ import annotations

import re

# Pattern to match string literals, quoted identifiers, and comments
# Order matters: check these before looking for keywords
_QUOTED_PATTERN = re.compile(
    r"""
    '(?:[^']*'')*[^']*'           # Single-quoted string ('' for escape)
    | "(?:[^"]*"")*[^"]*"         # Double-quoted string ("" for escape)
    | `[^`]*`                     # Backtick identifier (MySQL)
    | \[[^\]]*\]                  # Bracket identifier (SQL Server)
    | --[^\n]*                    # Single-line comment
    | /\*.*?\*/                   # Block comment
    """,
    re.VERBOSE | re.DOTALL,
)

_WHITESPACE_PATTERN = re.compile(r"\s+")
_KEYWORD_PATTERN = re.compile(r"[A-Za-z_]\w*")

_READONLY_KEYWORDS = frozenset({"SELECT", "SHOW", "DESCRIBE", "EXPLAIN"})
_WRITE_KEYWORDS = frozenset(
    {
        "INSERT",
        "CREATE",
        "ALTER",
        "DROP",
        "TRUNCATE",
        "DELETE",
        "UPDATE",
        "MERGE",
        "GRANT",
        "REVOKE",
        "REPLACE",
    }
)


def _strip_quoted(sql: str) -> str:
    """Remove string literals, quoted identifiers, and comments from SQL."""
    return _QUOTED_PATTERN.sub(" ", sql)


def _has_multiple_statements(sql: str) -> bool:
    """Check if SQL contains multiple statements (semicolon-separated)."""
    stripped = _strip_quoted(sql)
    # Find position of first semicolon
    first_semi = stripped.find(";")
    if first_semi == -1:
        return False
    # Check what's after the first semicolon
    after = stripped[first_semi + 1 :]
    # Trailing whitespace only is fine: "SELECT 1;  "
    after_stripped = after.strip()
    if not after_stripped:
        return False
    # Check if it's all semicolons with no whitespace between: "SELECT 1;;;"
    # vs semicolons with whitespace between: "SELECT 1; ; " (ambiguous)
    if all(c == ";" for c in after_stripped):
        # All semicolons after stripping - but was there whitespace between?
        # ";;;" → after=";;", fine
        # ";   ;" → after="   ;", has whitespace before semicolon = ambiguous
        for i, c in enumerate(after):
            if c.isspace():
                # Check if there's a semicolon after this whitespace
                if ";" in after[i + 1 :]:
                    return True
            elif c != ";":
                # Non-whitespace, non-semicolon = another statement
                return True
        return False
    # Has non-semicolon content = another statement
    return True


def _skip_whitespace(sql: str, pos: int) -> int:
    """Skip whitespace at position."""
    m = _WHITESPACE_PATTERN.match(sql, pos)
    return m.end() if m else pos


def _skip_cte(sql: str, pos: int) -> int:
    """Skip over CTE definitions (name AS (...), ...) to find main statement."""
    length = len(sql)
    expect_as = True  # After WITH/comma, expect: name AS (...)
    while pos < length:
        pos = _skip_whitespace(sql, pos)
        if pos >= length:
            break
        # Check for opening paren - skip balanced parens
        if sql[pos] == "(":
            depth = 1
            pos += 1
            while pos < length and depth > 0:
                if sql[pos] == "(":
                    depth += 1
                elif sql[pos] == ")":
                    depth -= 1
                pos += 1
            expect_as = False
            continue
        # Check for comma (another CTE follows)
        if sql[pos] == ",":
            pos += 1
            expect_as = True
            continue
        # Check for identifier/keyword
        m = _KEYWORD_PATTERN.match(sql, pos)
        if m:
            kw = m.group().upper()
            if expect_as:
                pos = m.end()
                if kw == "AS":
                    expect_as = False
                elif kw == "RECURSIVE":
                    pass  # WITH RECURSIVE - still expect CTE name
                continue
            # Not expecting AS - this should be the main statement keyword
            return pos
        pos += 1
    return pos


def _check_select_into(sql: str, pos: int) -> bool:
    """Check if SELECT statement contains INTO (making it a write operation)."""
    # Scan forward looking for INTO before FROM
    length = len(sql)
    while pos < length:
        pos = _skip_whitespace(sql, pos)
        if pos >= length:
            break
        m = _KEYWORD_PATTERN.match(sql, pos)
        if m:
            kw = m.group().upper()
            if kw == "INTO":
                return True
            if kw == "FROM":
                return False
            pos = m.end()
            continue
        # Skip other characters (*, columns, etc.)
        pos += 1
    return False


def is_readonly_sql(
    sql: str,
    *,
    extra_readonly: frozenset[str] = frozenset(),
    extra_write: frozenset[str] = frozenset(),
) -> bool | None:
    """
    Determine if a SQL statement is read-only.

    Args:
        sql: The SQL statement to analyze.
        extra_readonly: Additional keywords to treat as read-only (dialect-specific).
        extra_write: Additional keywords to treat as write operations (dialect-specific).

    Returns:
        True: Statement is definitely read-only (safe to auto-approve).
        False: Statement is definitely a write operation.
        None: Unknown or ambiguous (caller should prompt user).

    Notes:
        - Multiple statements (semicolon-separated) return None.
        - CTEs (WITH ... AS) are handled by analyzing the main statement.
        - Side-effect functions (e.g., SQLite's writefile) are NOT detected.
    """
    if _has_multiple_statements(sql):
        return None

    # Strip quoted content for keyword detection
    stripped = _strip_quoted(sql)

    readonly_keywords = _READONLY_KEYWORDS | extra_readonly
    write_keywords = _WRITE_KEYWORDS | extra_write

    pos = 0
    while pos < len(stripped):
        pos = _skip_whitespace(stripped, pos)
        if pos >= len(stripped):
            break
        m = _KEYWORD_PATTERN.match(stripped, pos)
        if not m:
            return None
        kw = m.group().upper()
        if kw == "WITH":
            pos = _skip_cte(stripped, m.end())
            continue
        if kw == "SELECT":
            # Check for SELECT INTO (write operation)
            if _check_select_into(stripped, m.end()):
                return False
            return True
        if kw in readonly_keywords:
            return True
        if kw in write_keywords:
            return False
        return None
    return None
