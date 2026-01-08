"""
GitHub CLI (gh) command handler for Dippy.

Approves read-only gh operations, blocks mutations.
"""

from typing import Optional


# Actions that only read data (second token after gh)
SAFE_ACTIONS = frozenset({
    # Common safe actions
    "list", "view", "status", "diff", "checks", "get", "search",
    "download", "watch", "verify", "verify-asset", "trusted-root",

    # gh auth
    "token",

    # gh codespace
    "logs", "ports",

    # gh project
    "field-list", "item-list",

    # gh ruleset
    "check",
})


# Actions that modify state
UNSAFE_ACTIONS = frozenset({
    "create", "delete", "edit", "close", "reopen",
    "merge", "comment", "review", "approve",
    "ready", "push", "sync",
})


# Flags that take an argument (skip these when finding action)
FLAGS_WITH_ARG = {"-R", "--repo", "-B", "--branch"}


def _get_action(tokens: list[str]) -> Optional[str]:
    """Get the action from gh command, skipping global flags."""
    # tokens[0] is 'gh', find the subcommand group and action
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in FLAGS_WITH_ARG:
            i += 2  # Skip flag and its argument
            continue
        if token.startswith("-"):
            i += 1
            continue
        # Found first non-flag token (subcommand group like 'pr', 'issue', etc.)
        if i + 1 < len(tokens):
            next_token = tokens[i + 1]
            if not next_token.startswith("-"):
                return next_token  # Return the action (e.g., 'list' in 'gh pr list')
        return token  # Just the subcommand group
    return None


def _check_api(tokens: list[str]) -> Optional[str]:
    """Check gh api command - approve GET requests, block mutations."""
    # tokens: ['gh', 'api', ...]
    args = tokens[2:] if len(tokens) > 2 else []

    # First pass: determine the method
    method = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"-X", "--method"}:
            if i + 1 < len(args):
                method = args[i + 1].upper()
            i += 2
        elif arg.startswith("-X") and len(arg) > 2:
            method = arg[2:].upper()
            i += 1
        elif arg.startswith("--method="):
            method = arg[9:].upper()
            i += 1
        else:
            i += 1

    # Explicit non-GET method is unsafe
    if method is not None and method != "GET":
        return None

    # Check for graphql queries vs mutations
    is_graphql_query = False
    for i, arg in enumerate(args):
        if arg in {"-f", "--raw-field"} and i + 1 < len(args):
            val = args[i + 1]
            if val.startswith("query="):
                query_content = val[6:]
                if "mutation" in query_content.lower():
                    return None
                is_graphql_query = "query" in query_content.lower() or "{" in query_content
        if arg.startswith(("--raw-field=query=", "-f=query=")):
            query_content = arg.split("=", 2)[2] if arg.count("=") >= 2 else ""
            if "mutation" in query_content.lower():
                return None
            is_graphql_query = "query" in query_content.lower() or "{" in query_content

    # GraphQL queries (not mutations) are safe
    if is_graphql_query:
        return "approve"

    # Check for params that imply POST
    has_mutation_flags = False
    for arg in args:
        if arg in {"-f", "--raw-field", "-F", "--field", "--input"}:
            has_mutation_flags = True
            break
        if arg.startswith(("--raw-field=", "--field=", "--input=")):
            has_mutation_flags = True
            break

    # Mutation flags only safe with explicit GET
    if has_mutation_flags and method != "GET":
        return None

    return "approve"


def _get_subcommand(tokens: list[str]) -> Optional[str]:
    """Get the subcommand from gh command, skipping global flags."""
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in FLAGS_WITH_ARG:
            i += 2  # Skip flag and its argument
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token
    return None


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a gh command should be approved.

    Returns:
        "approve" - Safe read-only operation
        None - Needs user confirmation
    """
    if len(tokens) < 2:
        return (None, "gh")

    subcommand = _get_subcommand(tokens)
    if not subcommand:
        return (None, "gh")

    # Special handlers for complex commands
    if subcommand == "api":
        result = _check_api(tokens)
        return (result, "gh api") if result else (None, "gh api")

    if subcommand == "status":
        return ("approve", "gh")  # Always read-only

    if subcommand == "browse":
        return ("approve", "gh")  # Opens browser, no mutations

    if subcommand == "search":
        return ("approve", "gh")  # All search subcommands are read-only

    # Get the action (second meaningful token)
    action = _get_action(tokens)

    if action in SAFE_ACTIONS:
        return ("approve", "gh")

    if action in UNSAFE_ACTIONS:
        return (None, "gh")

    # Unknown - ask user
    return (None, "gh")
