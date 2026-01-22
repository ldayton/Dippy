"""
Wget command handler for Dippy.

Wget downloads files by default, so most operations are unsafe.
Only --spider mode (check availability without downloading) is safe.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["wget"]


def classify(tokens: list[str]) -> Classification:
    """Classify wget command (spider mode only is safe)."""
    base = tokens[0] if tokens else "wget"
    if "--spider" in tokens:
        return Classification("approve", description=f"{base} --spider")
    return Classification("ask", description=f"{base} download")
