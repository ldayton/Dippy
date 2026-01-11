"""
Awk command handler for Dippy.

Awk is safe for text processing, but -f flag runs scripts
and the program can contain output redirects.
"""

import re

from dippy.cli import Classification

COMMANDS = ["awk", "gawk", "mawk", "nawk"]


# Patterns that indicate file output or command execution
# These match awk's print/printf redirection syntax: print > "file" or print | "cmd"
OUTPUT_REDIRECT_PATTERN = re.compile(
    r"""
    (?:print|printf)\s*[^}]*\s*      # print/printf followed by content
    (?:
        >\s*["']                      # > followed by quote (file redirect)
        |
        >>\s*["']                     # >> followed by quote (append redirect)
        |
        >\s*\(                        # > followed by ( (dynamic filename)
        |
        >>\s*\(                       # >> followed by ( (dynamic append)
        |
        >\s*\$                        # > followed by $ (variable filename)
        |
        \|\s*["']                     # | followed by quote (pipe to command)
    )
    """,
    re.VERBOSE,
)


def classify(tokens: list[str]) -> Classification:
    """Classify awk command (no script files or output redirects is safe)."""
    base = tokens[0] if tokens else "awk"
    # Check for -f/--file flag (runs script file)
    for t in tokens[1:]:
        if t == "-f" or t.startswith("-f"):
            return Classification("ask", description=f"{base} -f")
        if t == "--file" or t.startswith("--file="):
            return Classification("ask", description=f"{base} --file")

    # Find the awk program string (first non-flag argument)
    program = None
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("-"):
            # Skip flags and their arguments
            if t in ("-F", "-v", "--field-separator"):
                i += 2
                continue
            elif t.startswith("-F") or t.startswith("-v"):
                i += 1
                continue
            elif t.startswith("--field-separator=") or t.startswith("-v"):
                i += 1
                continue
            i += 1
            continue
        # This is the program
        program = t
        break

    if not program:
        return Classification("approve", description=base)

    # Check for system() calls
    if "system(" in program:
        return Classification("ask", description=base)

    # Check for output redirects using pattern matching
    if OUTPUT_REDIRECT_PATTERN.search(program):
        return Classification("ask", description=base)

    return Classification("approve", description=base)
