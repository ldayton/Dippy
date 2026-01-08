"""
Shell command handler for Dippy.

Handles bash, sh, zsh with -c flag (inline commands).
We approve if the inner command is safe.
"""

from typing import Optional


# Shells we handle
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "fish"})

# Not used directly but required by the handler protocol
SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if a shell -c command should be approved.

    Approves if the inner command passed to -c is safe.

    Returns:
        "approve" - Inner command is safe
        None - Needs user confirmation
    """
    if len(tokens) < 2:
        return None

    # Find -c flag (standalone or combined like -lc, -cl, -xcl, etc.)
    c_idx = None
    for i, tok in enumerate(tokens):
        if tok.startswith("-") and not tok.startswith("--") and "c" in tok:
            c_idx = i
            break

    if c_idx is None:
        # No -c flag - not running inline command, needs review
        return None

    if c_idx + 1 >= len(tokens):
        return None  # No command after -c

    inner_cmd = tokens[c_idx + 1]

    if not inner_cmd:
        return None

    # Import here to avoid circular dependency
    from dippy.dippy import check_command

    # Check the inner command
    result = check_command(inner_cmd)
    if result.get("decision") == "approve":
        return "approve"

    return None
