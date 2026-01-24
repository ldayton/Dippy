"""
Compression_tool command handler for Dippy.

macOS compression utility using the Compression library.
- -encode/-decode compress/decompress data
- Without -o, writes to stdout (safe)
- With -o, writes to specified file
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["compression_tool"]


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -o/--o flag."""
    for i, t in enumerate(tokens):
        if t in {"-o", "--o"} and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def _has_operation(tokens: list[str]) -> bool:
    """Check if -encode or -decode is present."""
    for t in tokens[1:]:
        if t in {"-encode", "-decode", "--encode", "--decode"}:
            return True
    return False


def classify(ctx: HandlerContext) -> Classification:
    """Classify compression_tool command."""
    tokens = ctx.tokens
    # -h is help
    if "-h" in tokens or "--h" in tokens:
        return Classification("allow", description="compression_tool")
    if not _has_operation(tokens):
        return Classification("allow", description="compression_tool")
    output_file = _extract_output_file(tokens)
    if output_file:
        return Classification(
            "allow",
            description="compression_tool",
            redirect_targets=(output_file,),
        )
    # No -o means stdout, which is safe
    return Classification("allow", description="compression_tool")
