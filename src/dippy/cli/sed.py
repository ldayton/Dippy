"""
Sed command handler for Dippy.

Sed is safe for text processing, but -i flag modifies files in place.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["sed"]


def classify(tokens: list[str]) -> Classification:
    """Classify sed command (no in-place modification is safe)."""
    base = tokens[0] if tokens else "sed"
    for t in tokens[1:]:
        if t == "-i" or t.startswith("-i"):
            return Classification("ask", description=f"{base} -i")
        if t == "--in-place" or t.startswith("--in-place"):
            return Classification("ask", description=f"{base} --in-place")
    return Classification("approve", description=base)
