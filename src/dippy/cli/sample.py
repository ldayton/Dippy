"""
Sample command handler for Dippy.

The sample command profiles a process and writes output to a file.
By default it writes to /tmp which is safe; custom paths need approval.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["sample"]


def classify(tokens: list[str]) -> Classification:
    """Classify sample command."""
    if len(tokens) < 2:
        return Classification("ask", description="sample (no target)")

    # Look for -file flag
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-file" and i + 1 < len(tokens):
            filepath = tokens[i + 1]
            # /tmp writes are safe (default behavior)
            if filepath.startswith("/tmp/") or filepath.startswith("/tmp"):
                return Classification("approve", description="sample -file /tmp/...")
            # Custom paths need approval
            return Classification("ask", description=f"sample -file {filepath}")
        i += 1

    # No -file flag means default /tmp output, which is safe
    return Classification("approve", description="sample (default /tmp output)")
