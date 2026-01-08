"""
Awk command handler for Dippy.

Awk is safe for text processing, but -f flag runs scripts
and the program can contain output redirects.
"""

import re
from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

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
    re.VERBOSE
)


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if an awk command should be approved.

    Rejects awk with -f (script file) or programs that write to files.

    Returns:
        "approve" - Read-only text processing
        None - Uses script file or writes to file, needs confirmation
    """
    # Check for -f/--file flag (runs script file)
    for i, t in enumerate(tokens[1:]):
        if t == "-f" or t.startswith("-f"):
            return (None, "awk")
        if t == "--file" or t.startswith("--file="):
            return (None, "awk")

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
        return ("approve", "awk")

    # Check for system() calls
    if "system(" in program:
        return (None, "awk")

    # Check for output redirects using pattern matching
    # This is more accurate than just checking for > character
    if OUTPUT_REDIRECT_PATTERN.search(program):
        return (None, "awk")

    return ("approve", "awk")
