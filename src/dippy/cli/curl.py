"""
Curl command handler for Dippy.

Approves GET/HEAD requests, blocks data-sending operations.
"""

from typing import Optional


# Flags that send data (always unsafe unless explicit GET)
DATA_FLAGS = frozenset({
    "-d", "--data",
    "--data-binary", "--data-raw", "--data-ascii", "--data-urlencode",
    "-F", "--form", "--form-string",
    "-T", "--upload-file",
    "--json",
})


# Flags that are always unsafe
UNSAFE_FLAGS = frozenset({
    "-K", "--config",
    "--ftp-create-dirs",
    "--mail-from", "--mail-rcpt",
})


# Safe HTTP methods (read-only)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


# Safe FTP commands (read-only)
SAFE_FTP_COMMANDS = frozenset({
    "PWD", "LIST", "NLST", "STAT", "SIZE",
    "MDTM", "NOOP", "HELP", "SYST", "TYPE",
    "PASV", "CWD", "CDUP", "FEAT",
})


# These don't need special handling in the new structure
SAFE_ACTIONS = frozenset()
UNSAFE_ACTIONS = frozenset()


def check(command: str, tokens: list[str]) -> tuple[Optional[str], str]:
    """
    Check if a curl command should be approved.

    Approves GET/HEAD requests without data-sending flags.

    Returns:
        "approve" - Safe read-only request
        None - Needs user confirmation
    """
    for i, t in enumerate(tokens):
        # Block always-unsafe flags
        if t in UNSAFE_FLAGS:
            return (None, "curl")

        # Block data/upload flags
        if t in DATA_FLAGS:
            return (None, "curl")

        # Check --flag=value variants
        for flag in DATA_FLAGS:
            if t.startswith(flag + "="):
                return (None, "curl")

        # Check -X/--request for non-safe methods
        if t in {"-X", "--request"}:
            if i + 1 < len(tokens):
                method = tokens[i + 1].upper()
                if method not in SAFE_METHODS:
                    return (None, "curl")

        # Also catch --request=METHOD and -XMETHOD
        if t.startswith("--request="):
            method = t.split("=", 1)[1].upper()
            if method not in SAFE_METHODS:
                return (None, "curl")
        if t.startswith("-X") and len(t) > 2 and not t.startswith("-X="):
            method = t[2:].upper()
            if method not in SAFE_METHODS:
                return (None, "curl")

        # Check -Q/--quote for FTP commands
        if t in {"-Q", "--quote"}:
            if i + 1 < len(tokens):
                ftp_cmd = tokens[i + 1].strip().strip("'\"").split()[0].upper()
                if ftp_cmd not in SAFE_FTP_COMMANDS:
                    return (None, "curl")

    return ("approve", "curl")
