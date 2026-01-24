"""
Say command handler for Dippy.

macOS text-to-speech utility. Safe by default (speaks to audio output),
but -o flag writes audio to a file.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["say"]


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -o/--output-file flag."""
    for i, t in enumerate(tokens):
        if t == "-o" and i + 1 < len(tokens):
            return tokens[i + 1]
        if t == "--output-file" and i + 1 < len(tokens):
            return tokens[i + 1]
        if t.startswith("--output-file="):
            return t[14:]
    return None


def classify(ctx: HandlerContext) -> Classification:
    """Classify say command."""
    tokens = ctx.tokens
    output_file = _extract_output_file(tokens)
    if output_file:
        return Classification(
            "allow",
            description="say -o",
            redirect_targets=(output_file,),
        )
    return Classification("allow", description="say")
