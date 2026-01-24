"""
Google Cloud CLI handler for Dippy.

Handles gcloud, gsutil, and bq commands.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["gcloud", "gsutil"]

# Safe action keywords - these are read-only operations
SAFE_ACTION_KEYWORDS = frozenset(
    {
        "describe",
        "list",
        "get",
        "show",
        "info",
        "status",
        "version",
        "get-credentials",  # Just configures kubectl
        "list-tags",
        "list-grantable-roles",
        "read",  # logging read, app logs read, etc.
        "configurations",  # gcloud topic configurations is help
    }
)

# Safe action prefixes
SAFE_ACTION_PREFIXES = ("list-", "describe-", "get-")

# Unsafe action keywords - these modify state (applied to last part only)
UNSAFE_ACTION_KEYWORDS = frozenset(
    {
        "create",
        "delete",
        "remove",
        "update",
        "set",
        "add",
        "patch",
        "start",
        "stop",
        "restart",
        "reset",
        "deploy",
        "undelete",
        "enable",
        "disable",
        "import",
        "export",
        "ssh",
        "scp",
        "login",
        "activate",
        "revoke",
        "configure-docker",
        "print-access-token",  # Sensitive operation
    }
)
# Note: "run" is NOT here because it's also a gcloud command group name

# Unsafe action patterns - match anywhere in action
UNSAFE_ACTION_PATTERNS = (
    "add-iam-policy-binding",
    "remove-iam-policy-binding",
    "set-iam-policy",
)

# Safe commands in specific groups
CONFIG_SAFE_COMMANDS = frozenset({"list", "get", "configurations"})

AUTH_SAFE_COMMANDS = frozenset({"list"})
# Most auth commands modify state

PROJECTS_SAFE_COMMANDS = frozenset(
    {"list", "describe", "get-ancestors", "get-iam-policy"}
)
PROJECTS_UNSAFE_COMMANDS = frozenset({"create", "delete", "undelete", "update"})


def get_description(tokens: list[str]) -> str:
    """Compute description for gcloud command."""
    base = tokens[0] if tokens else "gcloud"
    if len(tokens) < 2:
        return base
    if base == "gsutil":
        for token in tokens[1:]:
            if not token.startswith("-"):
                return f"gsutil {token}"
        return "gsutil"
    parts = _extract_parts(tokens[1:])
    if not parts:
        return base
    return f"{base} {' '.join(parts[:3])}"


def classify(ctx: HandlerContext) -> Classification:
    """Classify gcloud command."""
    tokens = ctx.tokens
    if len(tokens) < 2:
        base = tokens[0] if tokens else "gcloud"
        return Classification("ask", description=base)

    base = tokens[0]
    desc = get_description(tokens)

    # Handle gsutil separately
    if base == "gsutil":
        if _check_gsutil(tokens):
            return Classification("allow", description=desc)
        return Classification("ask", description=desc)

    parts = _extract_parts(tokens[1:])
    if not parts:
        return Classification("ask", description=base)

    # Help is always safe
    if "help" in parts or "--help" in tokens or "-h" in tokens:
        return Classification("allow", description=desc)

    # gcloud version/info/topic are safe
    if parts[0] in {"version", "info", "topic"}:
        return Classification("allow", description=desc)

    # Handle config group
    if parts[0] == "config":
        if len(parts) > 1:
            if parts[1] == "set":
                return Classification("ask", description=desc)
            if parts[1] == "configurations" and len(parts) > 2:
                if parts[2] in {"create", "activate", "delete"}:
                    return Classification("ask", description=desc)
                return Classification("allow", description=desc)
            if parts[1] in CONFIG_SAFE_COMMANDS:
                return Classification("allow", description=desc)
        return Classification("allow", description=desc)

    # Handle auth group - most commands modify state
    if parts[0] == "auth":
        if len(parts) > 1 and parts[1] in AUTH_SAFE_COMMANDS:
            return Classification("allow", description=desc)
        return Classification("ask", description=desc)

    # Handle projects group
    if parts[0] == "projects":
        if len(parts) > 1:
            action = parts[1]
            if action in PROJECTS_SAFE_COMMANDS:
                return Classification("allow", description=desc)
            if action in PROJECTS_UNSAFE_COMMANDS:
                return Classification("ask", description=desc)
            if "iam-policy-binding" in action or "iam-policy" in action:
                return Classification("ask", description=desc)
            return Classification("ask", description=desc)
        return Classification("allow", description=desc)

    # Skip beta/alpha prefix for action checking
    action_parts = [p for p in parts if p not in {"beta", "alpha"}]

    # Check for unsafe patterns in any part (takes precedence)
    for part in action_parts:
        for pattern in UNSAFE_ACTION_PATTERNS:
            if pattern in part:
                return Classification("ask", description=desc)

    # Check ALL parts for unsafe keywords (takes precedence over safe)
    for part in action_parts:
        if part in UNSAFE_ACTION_KEYWORDS:
            return Classification("ask", description=desc)

    # Check all parts for safe keywords
    for part in action_parts:
        if part in SAFE_ACTION_KEYWORDS:
            return Classification("allow", description=desc)
        for prefix in SAFE_ACTION_PREFIXES:
            if part.startswith(prefix):
                return Classification("allow", description=desc)

    return Classification("ask", description=desc)


def _extract_parts(tokens: list[str]) -> list[str]:
    """Extract command parts (service/subgroup/action), skipping flags and their arguments."""
    parts = []
    i = 0
    # Flags that consume the next token
    flags_with_arg = {
        "--project",
        "--region",
        "--zone",
        "--format",
        "--filter",
        "--cluster",
        "--location",
        "--instance",
        "--secret",
        "--service",
        "--keyring",
        "--member",
        "--role",
    }

    while i < len(tokens) and len(parts) < 6:
        token = tokens[i]

        # Skip flags
        if token.startswith("-"):
            if token in flags_with_arg and i + 1 < len(tokens):
                i += 2  # Skip flag and its argument
            elif "=" in token:
                i += 1  # Flag with value like --format=json
            else:
                i += 1  # Boolean flag
            continue

        # Skip what looks like values (URIs, paths, emails)
        if _looks_like_value(token):
            i += 1
            continue

        # This is a command part
        parts.append(token)
        i += 1

    return parts


def _looks_like_value(token: str) -> bool:
    """Check if token looks like a value rather than a command."""
    # GCS paths
    if token.startswith("gs://"):
        return True
    # GCR paths
    if token.startswith("gcr.io/"):
        return True
    # Resource paths
    if token.startswith("//"):
        return True
    # Email addresses
    if "@" in token:
        return True
    # Numeric values
    if token.isdigit():
        return True
    # Single quotes (filter expressions)
    if token.startswith("'"):
        return True
    return False


def _check_gsutil(tokens: list[str]) -> bool:
    """Check gsutil commands."""
    if len(tokens) < 2:
        return False

    action = None
    for token in tokens[1:]:
        if not token.startswith("-"):
            action = token
            break

    if not action:
        return False

    return action in {"ls", "cat", "stat", "du", "hash", "version", "help"}
