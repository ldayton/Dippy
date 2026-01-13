"""
Shell command handler for Dippy.

Handles bash, sh, zsh with -c flag (inline commands).
Delegates to inner command check.
"""

from dippy.cli import Classification

COMMANDS = ["bash", "sh", "zsh", "dash", "ksh", "fish"]


def classify(tokens: list[str]) -> Classification:
    """Classify shell command."""
    base = tokens[0] if tokens else "shell"
    if len(tokens) < 2:
        return Classification("ask", description=f"{base} interactive")

    # Find -c flag (standalone or combined like -lc, -cl, -xcl, etc.)
    c_idx = None
    for i, tok in enumerate(tokens):
        if tok.startswith("-") and not tok.startswith("--") and "c" in tok:
            c_idx = i
            break

    if c_idx is None:
        return Classification("ask", description=f"{base} interactive")

    if c_idx + 1 >= len(tokens):
        return Classification("ask", description=f"{base} -c (no command)")

    inner_cmd = tokens[c_idx + 1]
    if not inner_cmd:
        return Classification("ask", description=f"{base} -c (no command)")

    # Delegate to inner command check
    return Classification("delegate", inner_command=inner_cmd)
