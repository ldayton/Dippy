"""pre-commit handler for Dippy.

pre-commit manages git pre-commit hooks. Most commands modify files or hooks.
Only validation and help commands are safe.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["pre-commit"]

SAFE_ACTIONS = frozenset(
    {
        "validate-config",
        "validate-manifest",
        "help",
    }
)


def classify(tokens: list[str]) -> Classification:
    """Classify pre-commit command."""
    if len(tokens) < 2:
        return Classification("approve", description="pre-commit")  # Shows help

    action = tokens[1]

    if action in SAFE_ACTIONS:
        return Classification("approve", description=f"pre-commit {action}")

    # run, install, uninstall, autoupdate, etc. all modify files
    return Classification("ask", description=f"pre-commit {action}")
