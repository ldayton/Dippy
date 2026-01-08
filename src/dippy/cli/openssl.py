"""
OpenSSL command handler for Dippy.

OpenSSL has various commands, some are read-only (viewing certs)
and some modify files or do crypto operations.
"""

from typing import Optional


SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()

# Safe read-only subcommands
SAFE_COMMANDS = frozenset({
    "version",
    "help",
    "list",
})

# Commands that can be safe with certain flags
X509_SAFE_FLAGS = frozenset({
    "-noout",  # Don't output cert, just info
    "-text",
    "-subject", "-issuer",
    "-dates", "-startdate", "-enddate",
    "-serial", "-fingerprint",
    "-purpose", "-modulus",
    "-pubkey",
    "-in",  # Input file
})


def check(command: str, tokens: list[str]) -> Optional[str]:
    """Check if an openssl command should be approved."""
    if len(tokens) < 2:
        return None

    subcommand = tokens[1]

    # Safe subcommands
    if subcommand in SAFE_COMMANDS:
        return "approve"

    # x509 certificate viewing
    if subcommand == "x509":
        # If -noout is present, it's just viewing
        if "-noout" in tokens:
            return "approve"

    # s_client for connection testing (read-only)
    if subcommand == "s_client":
        return "approve"

    # Other subcommands need confirmation
    return None
