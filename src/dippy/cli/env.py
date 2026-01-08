"""
Env command handler for Dippy.

Env is used to set environment variables and run commands.
We need to extract and check the inner command.
"""

COMMANDS = ["env"]

# Env flags that take an argument
FLAGS_WITH_ARG = frozenset({
    "-u", "--unset",
    "-S", "--split-string",
    "-C", "--chdir",
})


def check(tokens: list[str]) -> bool:
    """Check if env command is safe."""
    if len(tokens) < 2:
        return True  # Just "env" prints environment

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
        return True  # Just env with no command

    # Check the inner command
    inner_tokens = tokens[i:]
    inner_cmd = " ".join(inner_tokens)

    from dippy.dippy import _check_single_command
    decision, _ = _check_single_command(inner_cmd)
    return decision == "approve"
