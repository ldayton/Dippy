"""
Env command handler for Dippy.

Env is used to set environment variables and run commands.
We need to extract and check the inner command.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

# Env flags that take an argument
FLAGS_WITH_ARG = frozenset({
    "-u", "--unset",
    "-S", "--split-string",
    "-C", "--chdir",
})


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if an env command should be approved.

    Extracts the inner command and checks it.
    """
    if len(tokens) < 2:
        return ("approve", "env")  # Just "env" prints environment

    # Find where the inner command starts
    i = 1
    while i < len(tokens):
        token = tokens[i]

        # -- ends flag processing
        if token == "--":
            i += 1
            break

        # Skip flags with arguments
        if token in FLAGS_WITH_ARG:
            i += 2
            continue

        # Skip other flags
        if token.startswith("-"):
            i += 1
            continue

        # Skip VAR=value assignments
        if "=" in token and not token.startswith("-"):
            i += 1
            continue

        # Found the inner command
        break

    if i >= len(tokens):
        return ("approve", "env")  # Just env with no command

    # Check the inner command
    inner_tokens = tokens[i:]
    inner_cmd = " ".join(inner_tokens)

    from dippy.dippy import _check_single_command
    decision, inner_desc = _check_single_command(inner_cmd)
    desc = f"env {inner_desc}"
    return (decision, desc)
