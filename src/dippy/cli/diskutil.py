"""Diskutil command handler for Dippy.

diskutil manipulates local disks, partitions, and volumes.
list/info/activity/listFilesystems are safe read operations.
mount/unmount/erase/partition etc modify disk state.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["diskutil"]

# Read-only verbs (case-insensitive matching done below)
SAFE_VERBS = frozenset({"list", "info", "information", "activity", "listfilesystems"})


def classify(ctx: HandlerContext) -> Classification:
    """Classify diskutil command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        return Classification("ask", description="diskutil")

    verb = tokens[1].lower()

    if verb in SAFE_VERBS:
        return Classification("allow", description=f"diskutil {verb}")

    return Classification("ask", description="diskutil")
