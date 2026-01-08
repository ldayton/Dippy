"""
Xargs command handler for Dippy.

Xargs executes commands with arguments from stdin.
We approve xargs if the inner command it runs is safe.
"""

from typing import Optional


# Flags that take an argument (skip these when finding the inner command)
FLAGS_WITH_ARG = frozenset({
    "-a", "--arg-file",
    "-d", "--delimiter",
    "-E", "-e", "--eof",
    "-I", "-J", "--replace",
    "-L", "-l", "--max-lines",
    "-n", "--max-args",
    "-P", "--max-procs",
    "-R",  # BSD: max replacements with -I
    "-s", "-S", "--max-chars",
    "--process-slot-var",
})

# Flags that make xargs interactive/unsafe regardless of command
UNSAFE_FLAGS = frozenset({"-p", "--interactive", "-o", "--open-tty"})


def _skip_flags(tokens: list[str], flags_with_arg: frozenset, stop_at_double_dash: bool = False) -> int:
    """Skip flags and their arguments, return index of first non-flag token."""
    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Stop at -- separator
        if stop_at_double_dash and token == "--":
            return i + 1

        # Not a flag - we found the command
        if not token.startswith("-"):
            return i

        # Check if this flag takes an argument
        if token in flags_with_arg:
            i += 2  # Skip flag and its argument
            continue

        # Handle combined short flags like -I{} or -d'\n'
        if len(token) > 2 and token[0] == "-" and token[1] != "-":
            # Check if base flag takes an arg (value is attached)
            base_flag = token[:2]
            if base_flag in flags_with_arg:
                i += 1
                continue

        # Handle --flag=value
        if "=" in token:
            i += 1
            continue

        # Regular flag without argument
        i += 1

    return i


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if an xargs command should be approved.

    Returns:
        (decision, description) where decision is "approve" or None.
    """
    if len(tokens) < 2:
        return (None, "xargs")

    # Check for unsafe flags (interactive mode)
    for token in tokens[1:]:
        if token == "--":
            break
        if token in UNSAFE_FLAGS:
            return (None, "xargs")
        if token.startswith(("--interactive", "--open-tty")):
            return (None, "xargs")

    # Find the inner command (skip xargs and its flags)
    inner_start = 1 + _skip_flags(tokens[1:], FLAGS_WITH_ARG, stop_at_double_dash=True)

    if inner_start >= len(tokens):
        return (None, "xargs")  # No inner command found

    inner_tokens = tokens[inner_start:]

    if not inner_tokens:
        return (None, "xargs")

    # Import here to avoid circular dependency
    from dippy.dippy import _check_single_command
    import shlex

    # Quote tokens that need it to preserve original structure
    inner_cmd = " ".join(shlex.quote(t) if ' ' in t or not t else t for t in inner_tokens)

    # Check the inner command - returns (decision, desc)
    decision, inner_desc = _check_single_command(inner_cmd)

    # Return xargs with inner command description
    desc = f"xargs {inner_desc}"
    return (decision, desc)
