"""
Prometheus command handler for Dippy.

Prometheus is a monitoring server and time-series database. Only help and version
flags are safe (informational only). Running the server itself is unsafe as it
starts a service, binds ports, creates lockfiles, and writes data to storage.
"""

from __future__ import annotations

from dippy.cli import Classification

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


def classify(tokens: list[str]) -> Classification:
    """Classify prometheus command.

    Only help/version flags are safe. Any other invocation starts the server
    which binds ports, creates lockfiles, and writes data - all unsafe operations.
    """
    base = tokens[0] if tokens else "prometheus"
    if len(tokens) < 2:
        # Just "prometheus" with no args starts the server
        return Classification("ask", description=f"{base} server")

    # Check if the only argument is a safe flag
    # Prometheus doesn't have subcommands - it's all flags
    for token in tokens[1:]:
        if token in SAFE_FLAGS:
            return Classification("approve", description=f"{base} {token}")

    # Any other flags or arguments start the server
    return Classification("ask", description=f"{base} server")
