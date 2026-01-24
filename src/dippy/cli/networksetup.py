"""Networksetup command handler for Dippy.

networksetup is the configuration tool for network system preferences.
-get*/-list*/-show*/-is*/-version/-help/-printcommands are safe.
-set*/-create*/-delete*/-remove*/-add*/-rename* etc modify settings.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["networksetup"]

# Safe option prefixes (read-only operations)
SAFE_PREFIXES = ("-get", "-list", "-show", "-is")

# Safe exact options
SAFE_OPTIONS = frozenset({"-version", "-help", "-printcommands"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify networksetup command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        return Classification("ask", description="networksetup")

    option = tokens[1].lower()

    if option in SAFE_OPTIONS:
        return Classification("allow", description=f"networksetup {option.lstrip('-')}")

    for prefix in SAFE_PREFIXES:
        if option.startswith(prefix):
            return Classification(
                "allow", description=f"networksetup {option.lstrip('-')}"
            )

    return Classification("ask", description="networksetup")
