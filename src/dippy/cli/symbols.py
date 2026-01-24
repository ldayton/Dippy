"""
Symbols command handler for Dippy.

macOS symbol information display tool.
- Most operations display symbol info (safe)
- -saveSignature writes signature to file (unsafe)
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["symbols"]


def _extract_save_signature(tokens: list[str]) -> str | None:
    """Extract the path from -saveSignature flag."""
    for i, t in enumerate(tokens):
        if t == "-saveSignature" and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def classify(ctx: HandlerContext) -> Classification:
    """Classify symbols command."""
    tokens = ctx.tokens
    save_path = _extract_save_signature(tokens)
    if save_path:
        return Classification(
            "allow",
            description="symbols -saveSignature",
            redirect_targets=(save_path,),
        )
    return Classification("allow", description="symbols")
