"""
Fzf command handler for Dippy.

Fzf is a fuzzy finder that reads from stdin and outputs selected items.
Most operations are safe (read-only filtering and display).

Unsafe operations:
- --listen-unsafe: Allows remote process execution via HTTP server
- --bind with execute/execute-silent/become: Delegates to inner command check
"""

from __future__ import annotations

import re

from dippy.cli import Classification, HandlerContext

COMMANDS = ["fzf"]

# Bind actions that execute external commands - delegate to inner command
EXEC_BIND_ACTIONS = frozenset(
    {
        "execute",
        "execute-silent",
        "become",
    }
)

# Pattern to extract command from action(cmd) syntax
PAREN_PATTERN = re.compile(r"(execute|execute-silent|become)\((.+)\)")

# Pattern to extract command from action:cmd syntax
COLON_PATTERN = re.compile(r"(execute|execute-silent|become):(\S+)")


def _extract_exec_command(bind_value: str) -> str | None:
    """Extract the command from execute/execute-silent/become actions."""
    # Try parenthesis syntax: execute(cmd)
    match = PAREN_PATTERN.search(bind_value)
    if match:
        return match.group(2)

    # Try colon syntax: execute:cmd
    match = COLON_PATTERN.search(bind_value)
    if match:
        return match.group(2)

    return None


def _has_exec_bind_action(bind_value: str) -> bool:
    """Check if a bind value contains execute/execute-silent/become actions."""
    for action in EXEC_BIND_ACTIONS:
        if f"{action}(" in bind_value:
            return True
        if f"{action}:" in bind_value:
            return True
        parts = bind_value.replace(",", ":").replace("+", ":").split(":")
        for part in parts:
            if part == action:
                return True
    return False


def classify(ctx: HandlerContext) -> Classification:
    """Classify fzf command."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "fzf"
    for i, token in enumerate(tokens):
        # Check for --listen-unsafe flag
        if token == "--listen-unsafe" or token.startswith("--listen-unsafe="):
            return Classification("ask", description=f"{base} --listen-unsafe")

        # Check for --bind with exec actions
        if token == "--bind" or token.startswith("--bind="):
            # Get the bind value
            if token == "--bind":
                if i + 1 < len(tokens):
                    bind_value = tokens[i + 1]
                else:
                    continue
            else:
                bind_value = token[7:]  # len("--bind=") == 7

            if _has_exec_bind_action(bind_value):
                # Try to extract and delegate the inner command
                inner_cmd = _extract_exec_command(bind_value)
                if inner_cmd:
                    return Classification(
                        "delegate",
                        inner_command=inner_cmd,
                        description=f"{base} --bind",
                    )
                # Couldn't extract command, ask for confirmation
                return Classification("ask", description=f"{base} --bind")

    return Classification("allow", description=base)
