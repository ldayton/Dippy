"""Fd command handler for Dippy.

Fd is a file search tool. All searches are safe, but --exec and --exec-batch
delegate to inner commands for safety checks.
"""

import shlex

from dippy.cli import Classification

COMMANDS = ["fd"]

# Execution flags that take commands as arguments
EXEC_FLAGS = frozenset({"-x", "--exec", "-X", "--exec-batch"})


def classify(tokens: list[str]) -> Classification:
    """Classify fd command by checking for execution flags."""
    if len(tokens) < 2:
        return Classification("approve", description="fd")

    # Check if any execution flag is present
    exec_flag_idx = None
    for i, token in enumerate(tokens[1:], start=1):
        if token in EXEC_FLAGS:
            exec_flag_idx = i
            break

    # No execution flag - just a search, safe to approve
    if exec_flag_idx is None:
        return Classification("approve", description="fd search")

    # Extract inner command after the execution flag
    inner_start = exec_flag_idx + 1
    if inner_start >= len(tokens):
        return Classification("ask", description="fd --exec (no command)")

    inner_tokens = tokens[inner_start:]
    if not inner_tokens:
        return Classification("ask", description="fd --exec (no command)")

    # Delegate to inner command check
    inner_cmd = " ".join(
        shlex.quote(t) if " " in t or not t else t for t in inner_tokens
    )
    return Classification(
        "delegate",
        inner_command=inner_cmd,
        description=f"fd --exec {inner_tokens[0]}",
    )
