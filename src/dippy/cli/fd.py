"""Fd command handler for Dippy.

Fd is a file search tool. All searches are safe, but --exec and --exec-batch
delegate to inner commands for safety checks.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext
from dippy.core.bash import bash_quote

COMMANDS = ["fd"]

# Execution flags that take commands as arguments
EXEC_FLAGS = frozenset({"-x", "--exec", "-X", "--exec-batch"})

# Map flags to descriptive form
FLAG_DISPLAY = {
    "-x": "-x (execute)",
    "-X": "-X (execute batch)",
    "--exec": "--exec (execute)",
    "--exec-batch": "--exec-batch (execute batch)",
}


def classify(ctx: HandlerContext) -> Classification:
    """Classify fd command by checking for execution flags."""
    tokens = ctx.tokens
    if len(tokens) < 2:
        return Classification("allow", description="fd")

    # Check if any execution flag is present
    exec_flag_idx = None
    exec_flag = None
    for i, token in enumerate(tokens[1:], start=1):
        if token in EXEC_FLAGS:
            exec_flag_idx = i
            exec_flag = token
            break

    # No execution flag - just a search, safe to approve
    if exec_flag_idx is None:
        return Classification("allow", description="fd")

    # Extract inner command after the execution flag
    inner_start = exec_flag_idx + 1
    if inner_start >= len(tokens):
        flag_desc = FLAG_DISPLAY.get(exec_flag, exec_flag)
        return Classification("ask", description=f"fd {flag_desc} (no command)")

    inner_tokens = tokens[inner_start:]
    if not inner_tokens:
        flag_desc = FLAG_DISPLAY.get(exec_flag, exec_flag)
        return Classification("ask", description=f"fd {flag_desc} (no command)")

    # Delegate to inner command check
    inner_cmd = " ".join(bash_quote(t) for t in inner_tokens)
    flag_desc = FLAG_DISPLAY.get(exec_flag, exec_flag)
    return Classification(
        "delegate",
        inner_command=inner_cmd,
        description=f"fd {flag_desc} {inner_tokens[0]}",
    )
