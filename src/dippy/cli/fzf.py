"""
Fzf command handler for Dippy.

Fzf is a fuzzy finder that reads from stdin and outputs selected items.
Most operations are safe (read-only filtering and display).

Unsafe operations:
- --listen-unsafe: Allows remote process execution via HTTP server
- --bind with execute/execute-silent/become: Can run arbitrary commands
"""

COMMANDS = ["fzf"]

# Unsafe bind actions that execute external commands
UNSAFE_BIND_ACTIONS = frozenset(
    {
        "execute",
        "execute-silent",
        "become",
    }
)


def check(tokens: list[str]) -> bool:
    """Check if fzf command is safe.

    Returns True to approve, False to ask user.
    """
    for i, token in enumerate(tokens):
        # Check for --listen-unsafe flag
        if token == "--listen-unsafe" or token.startswith("--listen-unsafe="):
            return False

        # Check for --bind with unsafe actions
        if token == "--bind" or token.startswith("--bind="):
            # Get the bind value
            if token == "--bind":
                # Value is in next token
                if i + 1 < len(tokens):
                    bind_value = tokens[i + 1]
                else:
                    continue
            else:
                # Value is after =
                bind_value = token[7:]  # len("--bind=") == 7

            if _has_unsafe_bind_action(bind_value):
                return False

    return True


def _has_unsafe_bind_action(bind_value: str) -> bool:
    """Check if a bind value contains unsafe actions.

    Bind format: KEY:ACTION or KEY:ACTION(ARGS) or KEY:ACTION:ARGS
    Multiple bindings separated by commas.
    """
    # Look for unsafe action patterns in the bind value
    # Actions can be: action(args), action:args, or just action
    for action in UNSAFE_BIND_ACTIONS:
        # Check for action( pattern (e.g., execute(vim {}))
        if f"{action}(" in bind_value:
            return True
        # Check for action: pattern (e.g., execute:vim {})
        if f"{action}:" in bind_value:
            return True
        # Check for action as standalone (e.g., in comma-separated list)
        # This handles cases like "enter:execute" without args
        # Split by common delimiters and check each part
        parts = bind_value.replace(",", ":").replace("+", ":").split(":")
        for part in parts:
            if part == action:
                return True

    return False
