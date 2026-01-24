"""
Binhex/applesingle/macbinary command handler for Dippy.

macOS file encoding utilities (all implemented as one tool).
- probe: check file encoding (safe)
- encode/decode: convert files (writes output)
- -c/--pipe: use stdin/stdout (safe)
- -o: specify output file
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["binhex", "applesingle", "macbinary"]


def _has_pipe_flag(tokens: list[str]) -> bool:
    """Check if -c/--pipe/--to-stdout flag is present."""
    for t in tokens:
        if t in {"-c", "--pipe", "--from-stdin", "--to-stdout"}:
            return True
    return False


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -o/--rename flag."""
    for i, t in enumerate(tokens):
        if t in {"-o", "--rename"} and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def _extract_output_dir(tokens: list[str]) -> str | None:
    """Extract the output directory from -C/--directory flag."""
    for i, t in enumerate(tokens):
        if t in {"-C", "--directory"} and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def classify(ctx: HandlerContext) -> Classification:
    """Classify binhex/applesingle/macbinary command."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "binhex"
    # Help/version are safe
    if "-h" in tokens or "--help" in tokens or "-V" in tokens or "--version" in tokens:
        return Classification("allow", description=base)
    # probe is safe (just checks encoding)
    if len(tokens) > 1 and tokens[1] == "probe":
        return Classification("allow", description=f"{base} probe")
    # With -c/--pipe, output goes to stdout (safe)
    if _has_pipe_flag(tokens):
        return Classification("allow", description=base)
    # Check for explicit output file
    output_file = _extract_output_file(tokens)
    if output_file:
        return Classification(
            "allow",
            description=base,
            redirect_targets=(output_file,),
        )
    # Check for output directory
    output_dir = _extract_output_dir(tokens)
    if output_dir:
        return Classification("ask", description=base)
    # encode/decode without -c writes to current directory
    if len(tokens) > 1 and tokens[1] in {"encode", "decode"}:
        return Classification("ask", description=f"{base} {tokens[1]}")
    # Default decode (no verb) also writes files
    return Classification("ask", description=base)
