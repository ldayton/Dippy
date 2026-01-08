"""
Wget command handler for Dippy.

Wget downloads files by default, so most operations are unsafe.
Only --spider mode (check availability without downloading) is safe.
"""

from typing import Optional


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a wget command should be approved.

    Only approves wget with --spider flag (no download, just check).

    Returns:
        "approve" - Spider mode (no download)
        None - Downloads files, needs confirmation
    """
    if "--spider" in tokens:
        return ("approve", "wget")
    return (None, "wget")
