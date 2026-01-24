"""Caffeinate command handler for Dippy.

caffeinate without a utility just prevents sleep (safe).
caffeinate with a utility runs it while preventing sleep (delegate).
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["caffeinate"]

# Flags that take no argument
FLAGS_NO_ARG = frozenset({"-d", "-i", "-m", "-s", "-u"})

# Flags that take an argument
FLAGS_WITH_ARG = frozenset({"-t", "-w"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify caffeinate command."""
    tokens = ctx.tokens
    if len(tokens) == 1:
        return Classification("allow", description="caffeinate")

    # Find where the utility starts
    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token in FLAGS_WITH_ARG:
            i += 2
            continue

        if token in FLAGS_NO_ARG:
            i += 1
            continue

        # Combined flags like -disu
        if token.startswith("-") and all(c in "dismu" for c in token[1:]):
            i += 1
            continue

        break

    if i >= len(tokens):
        return Classification("allow", description="caffeinate")

    # Delegate to utility
    inner_cmd = " ".join(tokens[i:])
    return Classification("delegate", inner_command=inner_cmd)
