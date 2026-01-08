"""
Find command handler for Dippy.

Find is mostly safe for searching, but has dangerous flags:
- -exec, -execdir: Execute arbitrary commands
- -ok, -okdir: Interactive execution
- -delete: Delete found files
"""

from typing import Optional


# Flags that make find unsafe (execute or delete)
UNSAFE_FLAGS = frozenset({
    "-exec", "-execdir",
    "-ok", "-okdir",
    "-delete",
})

# Not used directly but required by the handler protocol
SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if a find command should be approved.

    Approves find if it doesn't use execution or deletion flags.

    Returns:
        "approve" - Safe search operation
        None - Uses -exec/-delete, needs confirmation
    """
    # Check for unsafe flags
    for token in tokens:
        if token in UNSAFE_FLAGS:
            return None

    # No dangerous flags - approve
    return "approve"
