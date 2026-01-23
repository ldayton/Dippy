"""
Wget command handler for Dippy.

Wget downloads files by default, so most operations are unsafe.
Only --spider mode (check availability without downloading) is safe.
Output flags (-O, --output-document) return redirect_targets for config rule checking.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["wget"]


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -O/--output-document flag."""
    for i, t in enumerate(tokens):
        # -O file
        if t == "-O" and i + 1 < len(tokens):
            return tokens[i + 1]
        # --output-document file
        if t == "--output-document" and i + 1 < len(tokens):
            return tokens[i + 1]
        # --output-document=file
        if t.startswith("--output-document="):
            return t[18:]
    return None


def classify(tokens: list[str]) -> Classification:
    """Classify wget command (spider mode only is safe)."""
    base = tokens[0] if tokens else "wget"

    if "--spider" in tokens:
        return Classification("approve", description=f"{base} --spider")

    # Check for output file - return redirect_targets for config rule checking
    output_file = _extract_output_file(tokens)
    if output_file:
        return Classification(
            "approve",
            description=f"{base} download",
            redirect_targets=(output_file,),
        )

    return Classification("ask", description=f"{base} download")
