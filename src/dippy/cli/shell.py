"""
Shell command handler for Dippy.

Handles bash, sh, zsh with -c flag (inline commands).
We approve if the inner command is safe.
"""

COMMANDS = ["bash", "sh", "zsh", "dash", "ksh", "fish"]

# Shells we handle
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "fish"})


def check(tokens: list[str]) -> bool:
    """Check if shell -c command is safe."""
    if len(tokens) < 2:
        return False

    # Find -c flag (standalone or combined like -lc, -cl, -xcl, etc.)
    c_idx = None
    for i, tok in enumerate(tokens):
        if tok.startswith("-") and not tok.startswith("--") and "c" in tok:
            c_idx = i
            break

    if c_idx is None:
        return False  # No -c flag - not running inline command

    if c_idx + 1 >= len(tokens):
        return False  # No command after -c

    inner_cmd = tokens[c_idx + 1]
    if not inner_cmd:
        return False

    # Import here to avoid circular dependency
    from dippy.dippy import check_command

    # Check the inner command - returns dict with hookSpecificOutput
    result = check_command(inner_cmd)
    output = result.get("hookSpecificOutput", {})
    return output.get("permissionDecision") == "allow"
