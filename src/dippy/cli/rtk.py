"""rtk (Rust Token Killer) handler for Dippy.

rtk is a token-optimized CLI proxy that is typically prepended to bash
commands via a Claude Code PreToolUse hook. When both rtk and Dippy are
installed, Dippy sees commands like ``rtk git log`` and would otherwise
miss the ``git`` handler. This handler treats rtk as a transparent
wrapper so the inner command is analyzed directly.

Meta subcommands that do not wrap another command:
- ``rtk gain [--history]``: print token savings analytics (read-only)
- ``rtk discover``: analyze Claude Code history (read-only)
- ``rtk proxy <cmd>``: run the raw command without rtk's filtering; we
  still delegate to the inner command for safety analysis
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext
from dippy.core.bash import bash_join

COMMANDS = ["rtk"]

READ_ONLY_SUBCOMMANDS = frozenset({"gain", "discover"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify an rtk command."""
    tokens = ctx.tokens
    if len(tokens) == 1:
        return Classification("ask", description="rtk")

    sub = tokens[1]

    if sub in READ_ONLY_SUBCOMMANDS:
        return Classification("allow", description=f"rtk {sub}")

    if sub == "proxy":
        if len(tokens) == 2:
            return Classification("ask", description="rtk proxy")
        inner_cmd = bash_join(tokens[2:])
        return Classification("delegate", inner_command=inner_cmd)

    if sub.startswith("-"):
        return Classification("ask", description=f"rtk {sub}")

    inner_cmd = bash_join(tokens[1:])
    return Classification("delegate", inner_command=inner_cmd)
