"""
Azure CLI handler for Dippy.

Handles az commands.
"""

from typing import Optional


# Safe action keywords - if command contains these as action verbs, it's read-only
SAFE_ACTION_KEYWORDS = frozenset({
    "show", "list", "get", "exists", "query",
    "list-sizes", "list-skus", "list-offers", "list-publishers",
    "list-member", "list-definitions",
    "show-tags", "summarize", "logs",
    "check-health", "url", "download", "download-batch", "tail",
})

# Safe action prefixes - if command contains action starting with these
SAFE_ACTION_PREFIXES = ("list-", "show-", "get-")

# Exceptions: things that look safe but aren't (e.g., get- prefix but modifies state)
UNSAFE_EXCEPTIONS = frozenset({
    "get-credentials",  # az aks get-credentials modifies kubeconfig
})

# Unsafe action keywords - operations that modify state
UNSAFE_ACTION_KEYWORDS = frozenset({
    "create", "delete", "update", "set",
    "start", "stop", "restart",
    "add", "remove", "clear",
    "run", "invoke", "execute",
})

# Group-level commands that need subcommand checking
ACCOUNT_SAFE_COMMANDS = frozenset({"show", "list", "get-access-token"})
ACCOUNT_UNSAFE_COMMANDS = frozenset({"set", "clear"})

# Groups that are mostly read-only
SAFE_GROUPS = frozenset({
    "version", "find",
})

# Commands with safe/unsafe subcommands
SAFE_SUBCOMMANDS = {
    "bicep": {"version", "list-versions"},
}

# Groups that need confirmation
UNSAFE_GROUPS = frozenset({
    "login", "logout", "configure",
})

# Flags that consume the next argument (should be skipped)
FLAGS_WITH_ARG = frozenset({
    "--resource-group", "-g",
    "--subscription", "-s",
    "--name", "-n",
    "--output", "-o",
    "--query",
    "--location", "-l",
    "--ids", "--id",
    "--workspace-name", "--workspace",
    "--vault-name", "--vault",
    "--server", "--server-name",
    "--database", "--database-name",
    "--namespace-name", "--namespace",
    "--container-name", "--container",
    "--account-name", "--account",
    "--storage-account",
    "--registry", "--registry-name",
    "--repository",
    "--project", "--organization", "--org",
    "--pipeline-id", "--build-id", "--release-id",
    "--pool-id", "--group-id", "--team",
    "--assignee", "--scope",
    "--analytics-query", "--wiql",
    "--publisher", "--offer", "--sku", "--urn",
    "--start-time", "--end-time",
    "--resource", "--resource-type", "--resource-id",
})


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """Check if an az command should be approved or denied."""
    if len(tokens) < 2:
        return (None, "azure")

    # Collect command parts (service, subgroup, action), skipping flags and their args
    parts = _extract_parts(tokens[1:])

    if not parts:
        return (None, "azure")

    # Help is always safe
    if "help" in parts or "-h" in tokens or "--help" in tokens:
        return ("approve", "azure")

    # Check first part for unsafe groups
    if parts[0] in UNSAFE_GROUPS:
        return (None, "azure")

    # Check first part for safe groups
    if parts[0] in SAFE_GROUPS:
        return ("approve", "azure")

    # Handle account specially
    if parts[0] == "account":
        if len(parts) > 1:
            if parts[1] in ACCOUNT_SAFE_COMMANDS:
                return ("approve", "azure")
            if parts[1] in ACCOUNT_UNSAFE_COMMANDS:
                return (None, "azure")
        return ("approve", "azure")  # Just 'az account' shows current

    # Handle devops configure --list
    if parts[0] == "devops" and len(parts) > 1 and parts[1] == "configure":
        if "--list" in tokens:
            return ("approve", "azure")
        return (None, "azure")

    # Check commands with safe subcommands (e.g., az bicep version)
    if parts[0] in SAFE_SUBCOMMANDS and len(parts) > 1:
        if parts[1] in SAFE_SUBCOMMANDS[parts[0]]:
            return ("approve", "azure")

    # Check unsafe keywords FIRST (they take precedence)
    # This prevents "az vm delete list" from being approved just because "list" is safe
    for part in parts:
        if part in UNSAFE_ACTION_KEYWORDS:
            return (None, "azure")
        if part in UNSAFE_EXCEPTIONS:
            return (None, "azure")
        # set-policy, set-secret, etc.
        if part.startswith("set-"):
            return (None, "azure")

    # Check if any part is a safe action keyword
    for part in parts:
        if part in SAFE_ACTION_KEYWORDS:
            return ("approve", "azure")
        for prefix in SAFE_ACTION_PREFIXES:
            if part.startswith(prefix):
                return ("approve", "azure")

    # Unknown - ask user
    return (None, "azure")


def _extract_parts(tokens: list[str]) -> list[str]:
    """Extract command parts (service/subgroup/action), skipping flags and their arguments."""
    parts = []
    i = 0
    while i < len(tokens) and len(parts) < 5:
        token = tokens[i]

        # Skip flags
        if token.startswith("-"):
            if token in FLAGS_WITH_ARG and i + 1 < len(tokens):
                i += 2  # Skip flag and its argument
            elif "=" in token:
                i += 1  # Flag with value like --output=json
            else:
                i += 1  # Boolean flag
            continue

        # Looks like a positional argument (has slashes, dots, or is a value)
        if "/" in token or "." in token or "@" in token:
            i += 1
            continue

        # Skip what looks like values (UUIDs, numbers, etc.)
        if _looks_like_value(token):
            i += 1
            continue

        # This is a command part
        parts.append(token)
        i += 1

    return parts


def _looks_like_value(token: str) -> bool:
    """Check if token looks like a value rather than a command."""
    # UUIDs
    if len(token) == 36 and token.count("-") == 4:
        return True
    # Pure numbers
    if token.isdigit():
        return True
    # Looks like a resource path
    if token.startswith("/subscriptions/"):
        return True
    return False
