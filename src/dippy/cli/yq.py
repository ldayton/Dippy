"""yq handler for Dippy.

yq is a YAML/JSON/XML processor. It outputs to stdout by default,
but -i/--inplace modifies files in place.
"""

from dippy.cli import Classification

COMMANDS = ["yq"]


def classify(tokens: list[str]) -> Classification:
    """Classify yq command."""
    if not tokens:
        return Classification("ask", description="yq")

    for token in tokens[1:]:
        # Check for inplace flag
        if token in ("-i", "--inplace"):
            return Classification("ask", description="yq -i")
        # Handle -i=true or --inplace=true
        if token.startswith("-i=") or token.startswith("--inplace="):
            return Classification("ask", description="yq -i")

    return Classification("approve", description="yq")
