"""gzip/gunzip handler for Dippy.

gzip compresses files, gunzip decompresses them.
By default both modify files in-place (unsafe).
Safe when using stdout, list, or test modes.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["gzip", "gunzip"]

# Flags that make the command read-only/safe
SAFE_FLAGS = frozenset(
    {
        "-c",
        "--stdout",
        "--to-stdout",  # output to stdout, keep original
        "-l",
        "--list",  # list compressed file contents
        "-t",
        "--test",  # test integrity
        "--help",
        "--version",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify gzip/gunzip command."""
    tokens = ctx.tokens
    if not tokens:
        return Classification("ask", description="gzip")
    cmd = tokens[0]
    for token in tokens[1:]:
        # Handle combined short flags like -lv, -tv, -dc
        if token.startswith("-") and not token.startswith("--"):
            for char in token[1:]:
                if f"-{char}" in SAFE_FLAGS:
                    return Classification("allow", description=cmd)
        if token in SAFE_FLAGS:
            return Classification("allow", description=cmd)
    return Classification("ask", description=cmd)
