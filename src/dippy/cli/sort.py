"""
Sort command handler for Dippy.

Sort is safe for text processing, but -o flag writes to a file.
"""

from dippy.cli import Classification

COMMANDS = ["sort"]


def classify(tokens: list[str]) -> Classification:
    """Classify sort command (no output to file is safe)."""
    base = tokens[0] if tokens else "sort"
    for t in tokens[1:]:
        if t == "-o" or t.startswith("-o"):
            return Classification("ask", description=f"{base} -o (write to file)")
        if t == "--output" or t.startswith("--output"):
            return Classification("ask", description=f"{base} --output (write to file)")
    return Classification("approve", description=base)
