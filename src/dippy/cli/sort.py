"""
Sort command handler for Dippy.

Sort is safe for text processing, but -o flag writes to a file.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["sort"]


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -o/--output flag."""
    i = 1
    while i < len(tokens):
        t = tokens[i]

        # -o file or -ofile
        if t == "-o":
            if i + 1 < len(tokens):
                return tokens[i + 1]
            return None
        if t.startswith("-o") and len(t) > 2:
            return t[2:]

        # --output file or --output=file
        if t == "--output":
            if i + 1 < len(tokens):
                return tokens[i + 1]
            return None
        if t.startswith("--output="):
            return t[9:]

        i += 1

    return None


def classify(ctx: HandlerContext) -> Classification:
    """Classify sort command (no output to file is safe)."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "sort"

    output_file = _extract_output_file(tokens)

    if output_file:
        return Classification(
            "allow",
            description=f"{base} -o (write to file)",
            redirect_targets=(output_file,),
        )

    return Classification("allow", description=base)
