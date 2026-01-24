"""
Pkgutil command handler for Dippy.

macOS package utility for querying and manipulating installer packages.
- Query commands (--packages, --files, --pkg-info, etc.) are safe
- --forget, --learn modify receipt database
- --expand, --flatten, --bom create files
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["pkgutil"]

# Safe query commands
SAFE_COMMANDS = frozenset(
    {
        "--packages",
        "--pkgs",
        "--pkgs-plist",
        "--files",
        "--export-plist",
        "--pkg-info",
        "--pkg-info-plist",
        "--pkg-groups",
        "--groups",
        "--groups-plist",
        "--group-pkgs",
        "--file-info",
        "--file-info-plist",
        "--payload-files",
        "--check-signature",
        "--help",
        "-h",
    }
)

# Commands that modify state or create files
UNSAFE_COMMANDS = frozenset(
    {
        "--forget",  # Discards receipt data
        "--learn",  # Updates ACLs in receipt
        "--expand",  # Expands package to directory
        "--flatten",  # Creates flat package
        "--bom",  # Extracts BOM files to /tmp
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify pkgutil command."""
    tokens = ctx.tokens
    for t in tokens[1:]:
        if t in UNSAFE_COMMANDS:
            return Classification("ask", description=f"pkgutil {t}")
        if t in SAFE_COMMANDS:
            return Classification("allow", description=f"pkgutil {t}")
        # Handle --pkgs=REGEXP form
        if t.startswith("--pkgs="):
            return Classification("allow", description="pkgutil --pkgs")
    # No recognized command, default to ask
    return Classification("ask", description="pkgutil")
