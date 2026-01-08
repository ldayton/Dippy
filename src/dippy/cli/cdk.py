"""
AWS CDK command handler for Dippy.

CDK commands for infrastructure as code.
Most commands modify infrastructure, only a few are safe.
"""

from typing import Optional


# Safe CDK commands (read-only)
SAFE_ACTIONS = frozenset({
    "list", "ls",
    "diff",
    "synth", "synthesize",  # Generates CloudFormation, no deployment
    "metadata",
    "context",  # Needs special handling for --reset/--clear
    "docs",
    "doctor",
    "notices",
    "acknowledge", "ack",
})

# Unsafe CDK commands (modify infrastructure)
UNSAFE_ACTIONS = frozenset({
    "deploy",
    "destroy",
    "bootstrap",
    "import",
    "watch",
    "rollback",
    "gc",
    "refactor",
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """
    Check if a CDK command should be approved.

    Returns:
        "approve" - Safe read-only operation
        None - Needs user confirmation
    """
    if len(tokens) < 2:
        return None

    action = tokens[1]

    # Special handling for context command
    if action == "context":
        # --reset and --clear modify context
        for t in tokens:
            if t in {"--reset", "--clear"}:
                return None
        return "approve"

    if action in SAFE_ACTIONS:
        return "approve"

    if action in UNSAFE_ACTIONS:
        return None

    # Unknown - ask user
    return None
