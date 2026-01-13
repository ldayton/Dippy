"""
OpenSSL command handler for Dippy.

OpenSSL has various commands, some are read-only (viewing certs)
and some modify files or do crypto operations.
"""

from dippy.cli import Classification

COMMANDS = ["openssl"]

SAFE_COMMANDS = frozenset(
    {
        "version",
        "help",
        "list",
    }
)

# Subcommands that benefit from extra context (name isn't self-explanatory)
SUBCOMMAND_CONTEXT = {
    "req": "certificate request",
    "ca": "certificate authority",
    "enc": "encrypt/decrypt",
    "dgst": "digest/sign",
    "pkeyutl": "key operation",
    "rsautl": "RSA encrypt/sign",
    "rand": "random bytes",
    "cms": "cryptographic message",
    "ts": "timestamp",
}


def classify(tokens: list[str]) -> Classification:
    """Classify openssl command."""
    base = tokens[0] if tokens else "openssl"
    if len(tokens) < 2:
        return Classification("ask", description=base)

    subcommand = tokens[1]

    if subcommand in SAFE_COMMANDS:
        return Classification("approve", description=f"{base} {subcommand}")

    # x509 with -noout is just viewing
    if subcommand == "x509" and "-noout" in tokens:
        return Classification("approve", description=f"{base} x509 view")

    # s_client for connection testing
    if subcommand == "s_client":
        return Classification("approve", description=f"{base} s_client")

    # Build description - add context only if subcommand isn't self-explanatory
    context = SUBCOMMAND_CONTEXT.get(subcommand)
    if context:
        return Classification("ask", description=f"{base} {subcommand} ({context})")
    return Classification("ask", description=f"{base} {subcommand}")
