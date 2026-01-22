"""
AWS CDK command handler for Dippy.

CDK commands for infrastructure as code.
Most commands modify infrastructure, only a few are safe.
"""

from __future__ import annotations

from dippy.cli import Classification

COMMANDS = ["cdk"]

# Safe CDK commands (read-only)
SAFE_ACTIONS = frozenset(
    {
        "list",
        "ls",
        "diff",
        "synth",
        "synthesize",  # Generates CloudFormation, no deployment
        "metadata",
        "context",  # Needs special handling for --reset/--clear
        "docs",
        "doctor",
        "notices",
        "acknowledge",
        "ack",
    }
)


def classify(tokens: list[str]) -> Classification:
    """Classify CDK command."""
    base = tokens[0] if tokens else "cdk"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    action = tokens[1]
    desc = f"{base} {action}"

    # Special handling for context command
    if action == "context":
        if any(t in {"--reset", "--clear"} for t in tokens):
            return Classification("ask", description=desc)
        return Classification("approve", description=desc)

    if action in SAFE_ACTIONS:
        return Classification("approve", description=desc)
    return Classification("ask", description=desc)
