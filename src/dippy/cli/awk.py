"""
Awk command handler for Dippy.

Awk is safe for text processing, but -f flag runs scripts
and the program can contain output redirects.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if an awk command should be approved.

    Rejects awk with -f (script file) or programs that write to files.

    Returns:
        "approve" - Read-only text processing
        None - Uses script file or writes to file, needs confirmation
    """
    # Check for -f flag (runs script file)
    for i, t in enumerate(tokens[1:]):
        if t == "-f" or t.startswith("-f"):
            return None

    # Check program string for output redirects (> or >>) or system() calls
    for t in tokens[1:]:
        if not t.startswith("-"):
            # This is likely the awk program
            if ">" in t or ">>" in t:
                return None
            # system() can execute arbitrary commands
            if "system(" in t:
                return None

    return "approve"
