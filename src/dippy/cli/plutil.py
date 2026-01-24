"""
Plutil command handler for Dippy.

macOS property list utility.
- -p (print) and -lint (check syntax) are safe
- -convert modifies files (in-place or with -o)
- -insert, -replace, -remove modify plist contents
- -extract just prints extracted value (safe)
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["plutil"]

# Actions that modify files
UNSAFE_ACTIONS = frozenset({"-convert", "-insert", "-replace", "-remove"})


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -o flag."""
    for i, t in enumerate(tokens):
        if t == "-o" and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def _extract_input_files(tokens: list[str]) -> list[str]:
    """Extract input files that would be modified in-place."""
    files = []
    i = 1
    while i < len(tokens):
        t = tokens[i]
        # Skip flags with arguments
        if t in {
            "-o",
            "-convert",
            "-insert",
            "-replace",
            "-remove",
            "-extract",
            "-type",
        }:
            i += 2
            continue
        # Skip standalone flags
        if t.startswith("-"):
            i += 1
            continue
        # Non-flag argument is a file
        files.append(t)
        i += 1
    return files


def classify(ctx: HandlerContext) -> Classification:
    """Classify plutil command."""
    tokens = ctx.tokens
    has_unsafe_action = False
    action = None
    for t in tokens[1:]:
        if t in UNSAFE_ACTIONS:
            has_unsafe_action = True
            action = t
            break
    if not has_unsafe_action:
        return Classification("allow", description="plutil")
    # Check for -o flag (explicit output file)
    output_file = _extract_output_file(tokens)
    if output_file:
        return Classification(
            "allow",
            description=f"plutil {action}",
            redirect_targets=(output_file,),
        )
    # No -o means in-place modification of input files
    input_files = _extract_input_files(tokens)
    if input_files:
        return Classification(
            "allow",
            description=f"plutil {action}",
            redirect_targets=tuple(input_files),
        )
    return Classification("ask", description=f"plutil {action}")
