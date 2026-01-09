"""
Prometheus command handler for Dippy.

Prometheus is a monitoring server and time-series database. Only help and version
flags are safe (informational only). Running the server itself is unsafe as it
starts a service, binds ports, creates lockfiles, and writes data to storage.
"""

COMMANDS = ["prometheus"]

# Flags that are safe (informational only, don't start the server)
SAFE_FLAGS = frozenset(
    {
        "-h",
        "--help",
        "--help-long",
        "--help-man",
        "--version",
    }
)


def check(tokens: list[str]) -> bool:
    """Check if prometheus command is safe.

    Returns True to approve, False to ask user.

    Only help/version flags are safe. Any other invocation starts the server
    which binds ports, creates lockfiles, and writes data - all unsafe operations.
    """
    if len(tokens) < 2:
        # Just "prometheus" with no args starts the server
        return False

    # Check if the only argument is a safe flag
    # Prometheus doesn't have subcommands - it's all flags
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return True

    # Any other flags or arguments start the server
    return False
