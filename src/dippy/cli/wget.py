"""
Wget command handler for Dippy.

Wget downloads files by default, so most operations are unsafe.
Only --spider mode (check availability without downloading) is safe.
"""


def check(tokens: list[str]) -> bool:
    """Check if wget command is safe (spider mode only)."""
    return "--spider" in tokens
