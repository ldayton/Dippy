"""
Lipo command handler for Dippy.

macOS universal binary tool.
- -archs, -info, -detailed_info, -verify_arch are safe read operations
- -create, -extract, -extract_family, -remove, -replace, -thin write to -output
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["lipo"]

# Commands that only read/display info
SAFE_COMMANDS = frozenset({"-archs", "-info", "-detailed_info", "-verify_arch"})

# Commands that write to output file
WRITE_COMMANDS = frozenset(
    {"-create", "-extract", "-extract_family", "-remove", "-replace", "-thin"}
)


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -output flag."""
    for i, t in enumerate(tokens):
        if t in {"-output", "-o"} and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def classify(ctx: HandlerContext) -> Classification:
    """Classify lipo command."""
    tokens = ctx.tokens
    has_write_command = False
    for t in tokens[1:]:
        if t in SAFE_COMMANDS:
            return Classification("allow", description=f"lipo {t}")
        if t in WRITE_COMMANDS:
            has_write_command = True
    if has_write_command:
        output_file = _extract_output_file(tokens)
        if output_file:
            return Classification(
                "allow",
                description="lipo",
                redirect_targets=(output_file,),
            )
        return Classification("ask", description="lipo")
    # No recognized command, default to allow for info queries
    return Classification("allow", description="lipo")
