"""Bash quoting utilities for command reconstruction."""

from __future__ import annotations


def bash_quote(s: str) -> str:
    """Quote a string for safe use in bash.

    Uses single quotes (safest), with escape handling for embedded single quotes.
    Returns '' for empty strings. Returns unquoted if no special chars.
    """
    if not s:
        return "''"
    # Safe chars that don't need quoting
    safe = True
    for c in s:
        if not (c.isalnum() or c in "-_./=@:"):
            safe = False
            break
    if safe:
        return s
    # Single-quote, escaping embedded single quotes as '"'"'
    return "'" + s.replace("'", "'\"'\"'") + "'"


def bash_join(tokens: list[str]) -> str:
    """Join tokens into a bash command string with proper quoting."""
    return " ".join(bash_quote(t) for t in tokens)
