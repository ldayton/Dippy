"""
Xargs command handler for Dippy.

Xargs executes commands with arguments from stdin.
We approve xargs if the inner command it runs is safe.
"""

COMMANDS = ["xargs"]

# Flags that take an argument (skip these when finding the inner command)
FLAGS_WITH_ARG = frozenset(
    {
        "-a",
        "--arg-file",
        "-d",
        "--delimiter",
        "-E",
        "-e",
        "--eof",
        "-I",
        "-J",
        "--replace",
        "-L",
        "-l",
        "--max-lines",
        "-n",
        "--max-args",
        "-P",
        "--max-procs",
        "-R",  # BSD: max replacements with -I
        "-s",
        "-S",
        "--max-chars",
        "--process-slot-var",
    }
)

# Flags that make xargs interactive/unsafe regardless of command
UNSAFE_FLAGS = frozenset({"-p", "--interactive", "-o", "--open-tty"})


def _skip_flags(
    tokens: list[str], flags_with_arg: frozenset, stop_at_double_dash: bool = False
) -> int:
    """Skip flags and their arguments, return index of first non-flag token."""
    i = 0
    while i < len(tokens):
        token = tokens[i]

        if stop_at_double_dash and token == "--":
            return i + 1

        if not token.startswith("-"):
            return i

        if token in flags_with_arg:
            i += 2
            continue

        if len(token) > 2 and token[0] == "-" and token[1] != "-":
            base_flag = token[:2]
            if base_flag in flags_with_arg:
                i += 1
                continue

        if "=" in token:
            i += 1
            continue

        i += 1

    return i


def check(tokens: list[str]) -> bool:
    """Check if xargs command is safe."""
    if len(tokens) < 2:
        return False

    # Check for unsafe flags (interactive mode)
    for token in tokens[1:]:
        if token == "--":
            break
        if token in UNSAFE_FLAGS:
            return False
        if token.startswith(("--interactive", "--open-tty")):
            return False

    # Find the inner command (skip xargs and its flags)
    inner_start = 1 + _skip_flags(tokens[1:], FLAGS_WITH_ARG, stop_at_double_dash=True)

    if inner_start >= len(tokens):
        return False

    inner_tokens = tokens[inner_start:]
    if not inner_tokens:
        return False

    # Import here to avoid circular dependency
    from dippy.dippy import _check_single_command
    import shlex

    inner_cmd = " ".join(
        shlex.quote(t) if " " in t or not t else t for t in inner_tokens
    )
    decision, _ = _check_single_command(inner_cmd)
    return decision == "approve"
