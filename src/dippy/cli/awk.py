"""
Awk command handler for Dippy.

Awk is safe for text processing, but -f flag runs scripts
and the program can contain output redirects.
"""

import re

from dippy.cli import Classification

COMMANDS = ["awk", "gawk", "mawk", "nawk"]


# Patterns that indicate file output
FILE_REDIRECT_PATTERN = re.compile(
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
    )
    """,
    re.VERBOSE,
)

# Extract literal redirect targets: > "/path" or >> '/path'
LITERAL_REDIRECT_PATTERN = re.compile(
    r"""(?:print|printf)\s*[^}]*\s*>>?\s*["']([^"']+)["']""",
)

# Pattern for pipe to command
PIPE_PATTERN = re.compile(
    r"""
    (?:print|printf)\s*[^}]*\s*      # print/printf followed by content
    \|\s*["']                         # | followed by quote (pipe to command)
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
        return Classification("ask", description=f"{base} system()")

    # Check for pipe to command
    if PIPE_PATTERN.search(program):
        return Classification("ask", description=f"{base} pipe")

    # Check for file redirects
    if FILE_REDIRECT_PATTERN.search(program):
        # Extract literal paths that can be checked against redirect rules
        literal_targets = tuple(LITERAL_REDIRECT_PATTERN.findall(program))
        if literal_targets:
            # All redirects are to literal paths - let analyzer check them
            return Classification(
                "approve",
                description=f"{base} redirect",
                redirect_targets=literal_targets,
            )
        else:
            # Dynamic redirects (variables, expressions) - must ask
            return Classification("ask", description=f"{base} redirect")

    return Classification("approve", description=base)
