"""
Shell command handler for Dippy.

Handles bash, sh, zsh with -c flag (inline commands).
Delegates to inner command check.
"""

from dippy.cli import Classification

COMMANDS = ["bash", "sh", "zsh", "dash", "ksh", "fish"]


def classify(tokens: list[str]) -> Classification:
    """Classify shell command."""
    if len(tokens) < 2:
        return Classification("ask")

    # Find -c flag (standalone or combined like -lc, -cl, -xcl, etc.)
    c_idx = None
    for i, tok in enumerate(tokens):
        if tok.startswith("-") and not tok.startswith("--") and "c" in tok:
            c_idx = i
            break

    if c_idx is None:
        return Classification("ask")  # No -c flag - not running inline command

    if c_idx + 1 >= len(tokens):
        return Classification("ask")  # No command after -c

    inner_cmd = tokens[c_idx + 1]
    if not inner_cmd:
        return Classification("ask")

    # Delegate to inner command check
    return Classification("delegate", inner_command=inner_cmd)
