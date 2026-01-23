"""
Script command handler for Dippy.

The script command records terminal sessions or runs commands with a pseudo-TTY.
When running a command, delegates to inner command check.
"""

from __future__ import annotations

import shlex

from dippy.cli import Classification

COMMANDS = ["script"]

# Flags that take an argument
FLAGS_WITH_ARG = frozenset({"-t", "-T"})

# Flags that don't take arguments
FLAGS_NO_ARG = frozenset({"-a", "-d", "-e", "-F", "-k", "-p", "-q", "-r"})


def classify(tokens: list[str]) -> Classification:
    """Classify script command."""
    if len(tokens) < 2:
        return Classification("ask", description="script interactive")

    # Parse tokens to find file and command
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            i += 1
            break
        if tok.startswith("-"):
            if tok in FLAGS_WITH_ARG:
                i += 2
            elif tok in FLAGS_NO_ARG or (len(tok) > 1 and tok[1] != "-"):
                i += 1
            else:
                i += 1
        else:
            break

    if i >= len(tokens):
        return Classification("ask", description="script interactive")

    # tokens[i] is the file, tokens[i+1:] is the command (if any)
    command_tokens = tokens[i + 1 :]

    if not command_tokens:
        # Check if it's playback mode (-p flag)
        is_playback = any(
            t == "-p" or (t.startswith("-") and "p" in t and not t.startswith("--"))
            for t in tokens[1:i]
        )
        if is_playback:
            return Classification("approve", description="script -p (playback)")
        return Classification("ask", description="script interactive")

    # Delegate to inner command - shlex.join handles quoting for re-parse
    return Classification("delegate", inner_command=shlex.join(command_tokens))
