"""
Curl command handler for Dippy.

Approves GET/HEAD requests, blocks data-sending operations.
"""

COMMANDS = ["curl"]

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


def check(tokens: list[str]) -> bool:
    """Check if curl command is safe (GET/HEAD without data flags)."""
    for i, t in enumerate(tokens):
        # Block always-unsafe flags
        if t in UNSAFE_FLAGS:
            return False

        # Block data/upload flags
        if t in DATA_FLAGS:
            return False

        # Check --flag=value variants
        for flag in DATA_FLAGS:
            if t.startswith(flag + "="):
                return False

        # Check -X/--request for non-safe methods
        if t in {"-X", "--request"}:
            if i + 1 < len(tokens):
                method = tokens[i + 1].upper()
                if method not in SAFE_METHODS:
                    return False

        # Also catch --request=METHOD and -XMETHOD
        if t.startswith("--request="):
            method = t.split("=", 1)[1].upper()
            if method not in SAFE_METHODS:
                return False
        if t.startswith("-X") and len(t) > 2 and not t.startswith("-X="):
            method = t[2:].upper()
            if method not in SAFE_METHODS:
                return False

        # Check -Q/--quote for FTP commands
        if t in {"-Q", "--quote"}:
            if i + 1 < len(tokens):
                ftp_cmd = tokens[i + 1].strip().strip("'\"").split()[0].upper()
                if ftp_cmd not in SAFE_FTP_COMMANDS:
                    return False

    return True
