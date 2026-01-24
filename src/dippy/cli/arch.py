"""Arch command handler for Dippy.

arch without arguments prints architecture type (safe).
arch with arguments runs a program under a specific architecture (delegate).
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["arch"]

# Flags that take no argument
FLAGS_NO_ARG = frozenset({"-32", "-64", "-c", "-h"})

# Flags that take an argument
FLAGS_WITH_ARG = frozenset({"-arch", "--arch", "-d", "-e"})

# Architecture specifiers (used as -x86_64, -arm64, etc.)
ARCH_FLAGS = frozenset({"-i386", "-x86_64", "-x86_64h", "-arm64", "-arm64e"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify arch command."""
    tokens = ctx.tokens
    if len(tokens) == 1:
        return Classification("allow", description="arch")

    # Find where the inner command starts
    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token in FLAGS_NO_ARG or token in ARCH_FLAGS:
            i += 1
            continue

        if token in FLAGS_WITH_ARG:
            i += 2
            continue

        # Architecture flag without hyphen handled by -arch
        if token.startswith("-"):
            i += 1
            continue

        break

    if i >= len(tokens):
        return Classification("allow", description="arch")

    # Delegate to inner command
    inner_cmd = " ".join(tokens[i:])
    return Classification("delegate", inner_command=inner_cmd)
