"""
OpenSSL command handler for Dippy.

OpenSSL has various commands, some are read-only (viewing certs)
and some modify files or do crypto operations.
"""

COMMANDS = ["openssl"]

SAFE_COMMANDS = frozenset({
    "version",
    "help",
    "list",
})


def check(tokens: list[str]) -> bool:
    """Check if openssl command is safe."""
    if len(tokens) < 2:
        return False

    subcommand = tokens[1]

    if subcommand in SAFE_COMMANDS:
        return True

    # x509 with -noout is just viewing
    if subcommand == "x509" and "-noout" in tokens:
        return True

    # s_client for connection testing
    if subcommand == "s_client":
        return True

    return False
