"""Scutil command handler for Dippy.

scutil manages system configuration parameters.
--get/--dns/--proxy/-r/-w are safe read operations.
--set/--renew/--prefs/--nc and interactive mode are unsafe.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["scutil"]

# Read-only options
SAFE_OPTIONS = frozenset({"--get", "--dns", "--proxy", "-r", "-w"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify scutil command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        # Interactive mode
        return Classification("ask", description="scutil")

    option = tokens[1]

    if option in SAFE_OPTIONS:
        opt_name = option.lstrip("-")
        return Classification("allow", description=f"scutil {opt_name}")

    return Classification("ask", description="scutil")
