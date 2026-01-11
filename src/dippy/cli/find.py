"""
Find command handler for Dippy.

Find is mostly safe for searching, but has dangerous flags:
- -exec, -execdir: Execute arbitrary commands
- -ok, -okdir: Interactive execution
- -delete: Delete found files
"""

from dippy.cli import Classification

COMMANDS = ["find"]

UNSAFE_FLAGS = frozenset(
    {
        "-exec",
        "-execdir",
        "-ok",
        "-okdir",
        "-delete",
    }
)


def classify(tokens: list[str]) -> Classification:
    """Classify find command (no exec or delete is safe)."""
    base = tokens[0] if tokens else "find"
    for token in tokens:
        if token in UNSAFE_FLAGS:
            return Classification("ask", description=f"{base} {token}")
    return Classification("approve", description=base)
