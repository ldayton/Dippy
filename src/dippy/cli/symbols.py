"""
Symbols command handler for Dippy.

macOS symbol information display tool.
- Most operations display symbol info (safe)
- -saveSignature writes signature to file
- -symbolsPackageDir writes deep signatures to directory
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["symbols"]


def _extract_flag_arg(tokens: list[str], flag: str) -> str | None:
    """Extract the argument for a given flag."""
    for i, t in enumerate(tokens):
        if t == flag and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def classify(ctx: HandlerContext) -> Classification:
    """Classify symbols command."""
    tokens = ctx.tokens
    save_path = _extract_flag_arg(tokens, "-saveSignature")
    if save_path:
        return Classification(
            "allow",
            description="symbols -saveSignature",
            redirect_targets=(save_path,),
        )
    pkg_dir = _extract_flag_arg(tokens, "-symbolsPackageDir")
    if pkg_dir:
        return Classification(
            "allow",
            description="symbols -symbolsPackageDir",
            redirect_targets=(pkg_dir,),
        )
    return Classification("allow", description="symbols")
