"""
Xargs command handler for Dippy.

Xargs executes commands with arguments from stdin.
Delegates to inner command check.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext
from dippy.core.bash import bash_quote

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

# Context for unclear flags
FLAG_CONTEXT = {
    "-p": "prompt before execute",
    "-o": "open tty",
}


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


def classify(ctx: HandlerContext) -> Classification:
    """Classify xargs command by extracting the inner command."""
    tokens = ctx.tokens
    if len(tokens) < 2:
        return Classification("ask", description="xargs (no command)")

    # Check for unsafe flags (interactive mode)
    for token in tokens[1:]:
        if token == "--":
            break
        if token in UNSAFE_FLAGS:
            context = FLAG_CONTEXT.get(token)
            if context:
                return Classification("ask", description=f"xargs {token} ({context})")
            return Classification("ask", description=f"xargs {token}")
        if token.startswith("--interactive"):
            return Classification("ask", description="xargs --interactive")
        if token.startswith("--open-tty"):
            return Classification("ask", description="xargs --open-tty")

    # Find the inner command (skip xargs and its flags)
    inner_start = 1 + _skip_flags(tokens[1:], FLAGS_WITH_ARG, stop_at_double_dash=True)

    if inner_start >= len(tokens):
        return Classification("ask", description="xargs (no command)")

    inner_tokens = tokens[inner_start:]
    if not inner_tokens:
        return Classification("ask", description="xargs (no command)")

    # Delegate to inner command check
    inner_cmd = " ".join(bash_quote(t) for t in inner_tokens)
    return Classification("delegate", inner_command=inner_cmd)
