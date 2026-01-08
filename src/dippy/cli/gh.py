"""
GitHub CLI (gh) command handler for Dippy.

Approves read-only gh operations, blocks mutations.
"""


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


def _get_action(tokens: list[str]) -> str | None:
    """Get the action from gh command, skipping global flags."""
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in FLAGS_WITH_ARG:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        if i + 1 < len(tokens):
            next_token = tokens[i + 1]
            if not next_token.startswith("-"):
                return next_token
        return token
    return None


def _check_api(tokens: list[str]) -> bool:
    """Check gh api command - approve GET requests, block mutations."""
    args = tokens[2:] if len(tokens) > 2 else []

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

    if method is not None and method != "GET":
        return False

    is_graphql_query = False
    for i, arg in enumerate(args):
        if arg in {"-f", "--raw-field"} and i + 1 < len(args):
            val = args[i + 1]
            if val.startswith("query="):
                query_content = val[6:]
                if "mutation" in query_content.lower():
                    return False
                is_graphql_query = "query" in query_content.lower() or "{" in query_content
        if arg.startswith(("--raw-field=query=", "-f=query=")):
            query_content = arg.split("=", 2)[2] if arg.count("=") >= 2 else ""
            if "mutation" in query_content.lower():
                return False
            is_graphql_query = "query" in query_content.lower() or "{" in query_content

    if is_graphql_query:
        return True

    has_mutation_flags = False
    for arg in args:
        if arg in {"-f", "--raw-field", "-F", "--field", "--input"}:
            has_mutation_flags = True
            break
        if arg.startswith(("--raw-field=", "--field=", "--input=")):
            has_mutation_flags = True
            break

    if has_mutation_flags and method != "GET":
        return False

    return True


def _get_subcommand(tokens: list[str]) -> str | None:
    """Get the subcommand from gh command, skipping global flags."""
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token in FLAGS_WITH_ARG:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return token
    return None


def check(tokens: list[str]) -> bool:
    """Check if gh command is safe."""
    if len(tokens) < 2:
        return False

    subcommand = _get_subcommand(tokens)
    if not subcommand:
        return False

    if subcommand == "api":
        return _check_api(tokens)

    if subcommand in {"status", "browse", "search"}:
        return True

    action = _get_action(tokens)
    return action in SAFE_ACTIONS
