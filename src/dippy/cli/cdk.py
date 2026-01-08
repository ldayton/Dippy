"""
AWS CDK command handler for Dippy.

CDK commands for infrastructure as code.
Most commands modify infrastructure, only a few are safe.
"""


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


def check(tokens: list[str]) -> bool:
    """Check if CDK command is safe."""
    if len(tokens) < 2:
        return False

    action = tokens[1]

    # Special handling for context command
    if action == "context":
        return not any(t in {"--reset", "--clear"} for t in tokens)

    return action in SAFE_ACTIONS
