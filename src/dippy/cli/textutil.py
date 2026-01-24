"""
Textutil command handler for Dippy.

macOS text file conversion utility.
- -info displays file information (safe)
- -convert/-cat write files (unsafe unless -stdout is used)
- -output specifies output file
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["textutil"]

# Commands that write files
WRITE_COMMANDS = frozenset({"-convert", "-cat"})


def _has_stdout(tokens: list[str]) -> bool:
    """Check if -stdout flag is present."""
    return "-stdout" in tokens


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -output flag."""
    for i, t in enumerate(tokens):
        if t == "-output" and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def classify(ctx: HandlerContext) -> Classification:
    """Classify textutil command."""
    tokens = ctx.tokens
    has_write_command = False
    for t in tokens[1:]:
        if t in WRITE_COMMANDS:
            has_write_command = True
            break
    if not has_write_command:
        # -info, -help, or no command
        return Classification("allow", description="textutil")
    # Has -convert or -cat
    if _has_stdout(tokens):
        return Classification("allow", description="textutil")
    output_file = _extract_output_file(tokens)
    if output_file:
        return Classification(
            "allow",
            description="textutil",
            redirect_targets=(output_file,),
        )
    # Writes to input file location with new extension
    return Classification("ask", description="textutil")
