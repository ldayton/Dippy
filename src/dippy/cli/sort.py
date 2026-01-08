"""
Sort command handler for Dippy.

Sort is safe for text processing, but -o flag writes to a file.
"""


def check(tokens: list[str]) -> bool:
    """Check if sort command is safe (no output to file)."""
    for t in tokens[1:]:
        if t == "-o" or t.startswith("-o"):
            return False
        if t == "--output" or t.startswith("--output"):
            return False
    return True
