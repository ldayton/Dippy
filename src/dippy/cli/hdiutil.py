"""Hdiutil command handler for Dippy.

hdiutil manipulates disk images (attach, verify, create, etc).
help/info/verify/checksum/imageinfo/isencrypted/plugins/pmap are safe.
attach/detach/create/convert/mount etc modify or mount images.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["hdiutil"]

# Read-only verbs
SAFE_VERBS = frozenset({
    "help",
    "info",
    "verify",
    "checksum",
    "imageinfo",
    "isencrypted",
    "plugins",
    "pmap",
})


def classify(ctx: HandlerContext) -> Classification:
    """Classify hdiutil command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        return Classification("ask", description="hdiutil")

    verb = tokens[1]

    if verb in SAFE_VERBS:
        return Classification("allow", description=f"hdiutil {verb}")

    return Classification("ask", description="hdiutil")
