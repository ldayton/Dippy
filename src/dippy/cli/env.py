"""
Env command handler for Dippy.

Env is used to set environment variables and run commands.
Delegates to inner command check.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["env"]

# Env flags that take an argument
FLAGS_WITH_ARG = frozenset(
    {
        "-u",
        "--unset",
        "-S",
        "--split-string",
        "-C",
        "--chdir",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify env command by extracting the inner command."""
    tokens = ctx.tokens
    if len(tokens) < 2:
        return Classification("allow")  # Just "env" prints environment

    # Find where the inner command starts
    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token == "--":
            i += 1
            break

        if token in FLAGS_WITH_ARG:
            i += 2
            continue

        if token.startswith("-"):
            i += 1
            continue

        # Skip VAR=value assignments
        if "=" in token and not token.startswith("-"):
            i += 1
            continue

        break

    if i >= len(tokens):
        return Classification("allow")  # Just env with no command

    # Delegate to inner command check
    inner_tokens = tokens[i:]
    inner_cmd = " ".join(inner_tokens)
    return Classification("delegate", inner_command=inner_cmd)
