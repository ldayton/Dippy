"""Security command handler for Dippy.

security administers keychains, keys, certificates, and the Security framework.
find-*/get-*/show-*/dump-*/verify-*/list-smartcards/translocate-*/help/error/leaks are safe.
add-*/delete-*/create-*/set-*/import/export etc modify keychain state.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["security"]

# Purely read-only subcommands (no flags that modify state)
SAFE_SUBCOMMANDS = frozenset(
    {
        "help",
        "show-keychain-info",
        "dump-keychain",
        "find-generic-password",
        "find-internet-password",
        "find-key",
        "find-certificate",
        "find-identity",
        "get-identity-preference",
        "dump-trust-settings",
        "verify-cert",
        "error",
        "leaks",
        "list-smartcards",
        "translocate-policy-check",
        "translocate-status-check",
        "translocate-original-path",
        "requirement-evaluate",
    }
)


def classify(ctx: HandlerContext) -> Classification:
    """Classify security command."""
    tokens = ctx.tokens

    if len(tokens) < 2:
        return Classification("ask", description="security")

    subcommand = tokens[1]

    if subcommand in SAFE_SUBCOMMANDS:
        return Classification("allow", description=f"security {subcommand}")

    return Classification("ask", description="security")
