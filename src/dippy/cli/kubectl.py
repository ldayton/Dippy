"""
Kubectl command handler for Dippy.

Handles kubectl and similar Kubernetes CLI tools.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext
from dippy.core.bash import bash_join

COMMANDS = ["kubectl", "k"]

# Safe read-only actions
SAFE_ACTIONS = frozenset(
    {
        "get",
        "describe",
        "explain",
        "logs",
        "top",
        "cluster-info",
        "version",
        "api-resources",
        "api-versions",
        "config",  # Most config operations are read-only
        "auth",  # auth can-i is read-only
        "wait",  # Polling is read-only
        "diff",  # Shows differences without applying
        "plugin",  # Plugin management (list is read-only)
        "completion",  # Shell completion scripts
        "kustomize",  # Build kustomize manifests (output only)
    }
)


# Unsafe actions that modify cluster state
UNSAFE_ACTIONS = frozenset(
    {
        "create",
        "apply",
        "delete",
        "replace",
        "patch",
        "edit",
        "set",
        "scale",
        "autoscale",
        "rollout",
        "expose",
        "run",
        "attach",
        "exec",  # exec can modify
        "cp",
        "label",
        "annotate",
        "taint",
        "cordon",
        "uncordon",
        "drain",
        "port-forward",  # Creates a network tunnel
        "proxy",  # Creates proxy to API server
        "debug",  # Debug running pods
        "certificate",  # Certificate management (approve/deny)
    }
)


# Safe subcommands for multi-level commands
SAFE_SUBCOMMANDS = {
    "config": {
        "view",
        "get-contexts",
        "get-clusters",
        "current-context",
        "get-users",
    },
    "auth": {"can-i", "whoami"},
    "rollout": {"status", "history"},
}


# Unsafe subcommands
UNSAFE_SUBCOMMANDS = {
    "config": {
        "set",
        "set-context",
        "set-cluster",
        "set-credentials",
        "delete-context",
        "delete-cluster",
        "delete-user",
        "use-context",
        "use",
        "rename-context",
    },
    "rollout": {"restart", "pause", "resume", "undo"},
}


SECRET_RESOURCES = frozenset({"secret", "secrets"})

SAFE_OUTPUT_FORMATS = frozenset({"name", "wide"})

# Flags (after the verb) that consume the next token as a value
_POST_VERB_FLAGS_WITH_ARG = frozenset(
    {
        "-o",
        "--output",
        "-n",
        "--namespace",
        "-l",
        "--selector",
        "-f",
        "--filename",
        "--field-selector",
        "--sort-by",
        "--template",
        "--context",
        "--cluster",
    }
)


def _is_secret_data_exposure(
    tokens: list[str],
    rest: list[str],
    word_has_expansions: tuple[bool, ...] = (),
    rest_offset: int = 0,
) -> bool:
    """Check if a get command targets secrets with a data-exposing output format.

    Scans rest for the resource type and full tokens for -o (which can appear
    before or after the verb).  Tokens built from a bash expansion are treated
    conservatively, since they could resolve to a secret resource or a
    data-exposing format at runtime.
    """
    # Find resource type: first non-flag token in rest
    resource_type = None
    resource_abs_pos = None
    i = 0
    while i < len(rest):
        token = rest[i]
        if token in _POST_VERB_FLAGS_WITH_ARG:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        resource_type = token
        resource_abs_pos = rest_offset + i
        break

    if resource_type is None:
        return False

    # If the resource came from an expansion, it could resolve to "secret"
    if _has_expansion(word_has_expansions, resource_abs_pos):
        return True

    # Handle comma-separated resources (e.g., "secret,configmap") and
    # type/name syntax (e.g., "secret/my-secret")
    parts = resource_type.split(",")
    if not any(p.split("/")[0] in SECRET_RESOURCES for p in parts):
        return False

    # Resource IS secrets -- if any remaining token came from an expansion, it
    # could inject a data-exposing format like -o yaml
    if _has_expansion_after(word_has_expansions, resource_abs_pos + 1):
        return True

    # Find output format from full token list (-o can appear before or after verb)
    output_format = None
    for j, token in enumerate(tokens):
        if token in ("-o", "--output") and j + 1 < len(tokens):
            output_format = tokens[j + 1]
            break
        if token.startswith("--output="):
            output_format = token[len("--output=") :]
            break
        if len(token) > 2 and token[:2] == "-o" and token[2] != "-":
            output_format = token[2:]
            break

    if output_format is None:
        return False

    # Extract format name before any = (e.g., "jsonpath='{.data}'" -> "jsonpath")
    format_name = output_format.split("=")[0]
    return format_name not in SAFE_OUTPUT_FORMATS


def _extract_exec_inner_command(tokens: list[str]) -> list[str] | None:
    """Extract command from kubectl exec args (after -- separator)."""
    try:
        sep_idx = tokens.index("--")
        result = tokens[sep_idx + 1 :]
        return result if result else None
    except ValueError:
        return None  # No -- separator


def _has_expansion(word_has_expansions: tuple[bool, ...], pos: int) -> bool:
    """Whether the token at pos was built from a bash expansion (runtime value)."""
    return 0 <= pos < len(word_has_expansions) and word_has_expansions[pos]


def _has_expansion_after(word_has_expansions: tuple[bool, ...], start: int) -> bool:
    """Whether any token at or after start was built from a bash expansion."""
    return any(word_has_expansions[start:])


def classify(ctx: HandlerContext) -> Classification:
    """Classify kubectl command."""
    tokens = ctx.tokens
    expansions = ctx.word_has_expansions
    base = tokens[0] if tokens else "kubectl"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    # Find the action (skip global flags)
    action = None
    action_idx = 1

    while action_idx < len(tokens):
        token = tokens[action_idx]

        if token.startswith("-"):
            if token in {
                "-n",
                "--namespace",
                "-l",
                "--selector",
                "-o",
                "--output",
                "--context",
                "--cluster",
                "-f",
                "--filename",
            }:
                action_idx += 2
                continue
            action_idx += 1
            continue

        action = token
        break

    if not action:
        return Classification("ask", description=base)

    rest = tokens[action_idx + 1 :] if action_idx + 1 < len(tokens) else []
    rest_offset = action_idx + 1
    desc = f"{base} {action}"

    # Check for subcommands first (config/auth/rollout)
    if action in SAFE_SUBCOMMANDS and rest:
        for idx, token in enumerate(rest):
            if not token.startswith("-"):
                abs_pos = rest_offset + idx
                if _has_expansion(expansions, abs_pos):
                    return Classification("ask", description=desc)
                if token in SAFE_SUBCOMMANDS[action]:
                    # config view --raw exposes unredacted kubeconfig credentials
                    if action == "config" and token == "view":
                        if "--raw" in rest or _has_expansion_after(
                            expansions, abs_pos + 1
                        ):
                            return Classification("ask", description=f"{desc} {token}")
                    return Classification("allow", description=f"{desc} {token}")
                break

    if action in UNSAFE_SUBCOMMANDS and rest:
        for idx, token in enumerate(rest):
            if not token.startswith("-"):
                abs_pos = rest_offset + idx
                if _has_expansion(expansions, abs_pos):
                    return Classification("ask", description=desc)
                if token in UNSAFE_SUBCOMMANDS[action]:
                    return Classification("ask", description=f"{desc} {token}")
                break

    # Sensitive data checks (before blanket safe-action approval)
    if action == "get" and _is_secret_data_exposure(
        tokens, rest, expansions, rest_offset
    ):
        return Classification("ask", description=f"{desc} (secret data)")

    # Simple safe actions
    if action in SAFE_ACTIONS:
        return Classification("allow", description=desc)

    # Handle exec - delegate to inner command with remote mode
    if action == "exec":
        inner_tokens = _extract_exec_inner_command(rest)
        if inner_tokens:
            inner_cmd = bash_join(inner_tokens)
            return Classification(
                "delegate", inner_command=inner_cmd, description=desc, remote=True
            )
        return Classification("ask", description=desc)

    return Classification("ask", description=desc)
