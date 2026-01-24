"""Defaults command handler for Dippy.

defaults reads and writes macOS user configuration.
read/read-type/domains/find/help are safe, write/rename/delete are not.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["defaults"]

SAFE_ACTIONS = frozenset({"read", "read-type", "domains", "find", "help"})

# Global flags that can appear before the action
GLOBAL_FLAGS = frozenset({"-currentHost", "-host"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify defaults command."""
    tokens = ctx.tokens

    # Find the action (skip global flags)
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in GLOBAL_FLAGS:
            i += 2 if token == "-host" else 1
            continue
        break

    if i >= len(tokens):
        return Classification("ask", description="defaults")

    action = tokens[i]

    if action in SAFE_ACTIONS:
        return Classification("allow", description=f"defaults {action}")

    return Classification("ask", description=f"defaults {action}")
