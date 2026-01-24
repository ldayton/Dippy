"""Open command handler for Dippy.

open launches files/directories/URLs in their default applications.
Only -R (reveal in Finder) is safe - everything else launches external apps.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["open"]


def classify(ctx: HandlerContext) -> Classification:
    """Classify open command."""
    tokens = ctx.tokens

    # -R reveals in Finder without launching apps
    if "-R" in tokens:
        return Classification("allow", description="open -R")

    return Classification("ask", description="open")
