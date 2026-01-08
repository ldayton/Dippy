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


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a shell -c command should be approved.

    Returns:
        (decision, description) where decision is "approve" or None.
    """
    shell = tokens[0]

    if len(tokens) < 2:
        return (None, shell)

    # Find -c flag (standalone or combined like -lc, -cl, -xcl, etc.)
    c_idx = None
    for i, tok in enumerate(tokens):
        if tok.startswith("-") and not tok.startswith("--") and "c" in tok:
            c_idx = i
            break

    if c_idx is None:
        # No -c flag - not running inline command, needs review
        return (None, shell)

    if c_idx + 1 >= len(tokens):
        return (None, shell)  # No command after -c

    inner_cmd = tokens[c_idx + 1]

    if not inner_cmd:
        return (None, shell)

    # Import here to avoid circular dependency
    from dippy.dippy import check_command

    # Check the inner command - returns dict with hookSpecificOutput
    result = check_command(inner_cmd)
    output = result.get("hookSpecificOutput", {})
    decision = output.get("permissionDecision")
    inner_reason = output.get("permissionDecisionReason", "").removeprefix("🐤 ")

    desc = f"{shell} -c {inner_reason}" if inner_reason else shell

    if decision == "allow":
        return ("approve", desc)

    return (None, desc)
