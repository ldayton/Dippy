"""
Pytest command handler for Dippy.

Pytest runs arbitrary Python code, so test execution requires approval.
Safe operations like --version, --help, --collect-only are auto-approved.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["pytest"]

SAFE_FLAGS = frozenset(
    {
        "--version",
        "-V",
        "--help",
        "-h",
        "--collect-only",
        "--co",
    }
)


def classify(tokens: list[str]) -> Classification:
    """Classify pytest command."""
    if len(tokens) < 2:
        return Classification("ask", description="pytest run")

    # Check if any safe flag is present
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return Classification("approve", description=f"pytest {token}")

    return Classification("ask", description="pytest run")
