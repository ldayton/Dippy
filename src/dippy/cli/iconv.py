"""iconv handler for Dippy."""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["iconv"]


def classify(ctx: HandlerContext) -> Classification:
    """Classify iconv command for safety.

    iconv converts text encoding. Safe by default (writes to stdout),
    but -o/--output writes to a file which needs redirect rule checking.
    """
    tokens = ctx.tokens

    # Look for -o or --output flag
    output_file = None
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t == "-o" or t == "--output":
            if i + 1 < len(tokens):
                output_file = tokens[i + 1]
            i += 2
            continue
        if t.startswith("-o"):
            output_file = t[2:]
            i += 1
            continue
        if t.startswith("--output="):
            output_file = t[9:]
            i += 1
            continue
        i += 1

    if output_file:
        return Classification(
            "allow",
            description="iconv -o",
            redirect_targets=(output_file,),
        )

    return Classification("allow", description="iconv")
