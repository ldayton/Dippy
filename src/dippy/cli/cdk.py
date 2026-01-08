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


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a CDK command should be approved.

    Returns:
        "approve" - Safe read-only operation
        None - Needs user confirmation
    """
    if len(tokens) < 2:
        return (None, "cdk")

    action = tokens[1]

    # Special handling for context command
    if action == "context":
        # --reset and --clear modify context
        for t in tokens:
            if t in {"--reset", "--clear"}:
                return (None, "cdk")
        return ("approve", "cdk")

    if action in SAFE_ACTIONS:
        return ("approve", "cdk")

    if action in UNSAFE_ACTIONS:
        return (None, "cdk")

    # Unknown - ask user
    return (None, "cdk")
