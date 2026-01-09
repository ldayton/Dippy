"""
Find command handler for Dippy.

Find is mostly safe for searching, but has dangerous flags:
- -exec, -execdir: Execute arbitrary commands
- -ok, -okdir: Interactive execution
- -delete: Delete found files
"""

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


def check(tokens: list[str]) -> bool:
    """Check if find command is safe (no exec or delete)."""
    for token in tokens:
        if token in UNSAFE_FLAGS:
            return False
    return True
