"""
Curl command handler for Dippy.

Approves GET/HEAD requests, blocks data-sending operations.
Output flags (-o, --output) return redirect_targets for config rule checking.
"""

from __future__ import annotations

from dippy.cli import Classification, HandlerContext

COMMANDS = ["curl"]

# Output flags that write to files
OUTPUT_FLAGS = frozenset({"-o", "--output"})

# Flags that send data (always unsafe unless explicit GET)
DATA_FLAGS = frozenset(
    {
        "-d",
        "--data",
        "--data-binary",
        "--data-raw",
        "--data-ascii",
        "--data-urlencode",
        "-F",
        "--form",
        "--form-string",
        "-T",
        "--upload-file",
        "--json",
    }
)


# Flags that are always unsafe
UNSAFE_FLAGS = frozenset(
    {
        "-K",
        "--config",
        "--ftp-create-dirs",
        "--mail-from",
        "--mail-rcpt",
    }
)


# Safe HTTP methods (read-only)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


# Safe FTP commands (read-only)
SAFE_FTP_COMMANDS = frozenset(
    {
        "PWD",
        "LIST",
        "NLST",
        "STAT",
        "SIZE",
        "MDTM",
        "NOOP",
        "HELP",
        "SYST",
        "TYPE",
        "PASV",
        "CWD",
        "CDUP",
        "FEAT",
    }
)


def _extract_output_file(tokens: list[str]) -> str | None:
    """Extract the output file from -o/--output flag."""
    for i, t in enumerate(tokens):
        # -o file
        if t == "-o" and i + 1 < len(tokens):
            return tokens[i + 1]
        # -ofile (no space)
        if t.startswith("-o") and len(t) > 2 and not t.startswith("-o="):
            return t[2:]
        # --output file
        if t == "--output" and i + 1 < len(tokens):
            return tokens[i + 1]
        # --output=file
        if t.startswith("--output="):
            return t[9:]
    return None


def classify(ctx: HandlerContext) -> Classification:
    """Classify curl command (GET/HEAD without data flags is safe)."""
    tokens = ctx.tokens
    base = tokens[0] if tokens else "curl"
    for i, t in enumerate(tokens):
        # Block always-unsafe flags
        if t in UNSAFE_FLAGS:
            return Classification("ask", description=f"{base} {t}")

        # Block data/upload flags
        if t in DATA_FLAGS:
            return Classification("ask", description=f"{base} {t}")

        # Check --flag=value variants
        for flag in DATA_FLAGS:
            if t.startswith(flag + "="):
                return Classification("ask", description=f"{base} {flag}")

        # Check -X/--request for non-safe methods
        if t in {"-X", "--request"}:
            if i + 1 < len(tokens):
                method = tokens[i + 1].upper()
                if method not in SAFE_METHODS:
                    return Classification("ask", description=f"{base} {method}")

        # Also catch --request=METHOD and -XMETHOD
        if t.startswith("--request="):
            method = t.split("=", 1)[1].upper()
            if method not in SAFE_METHODS:
                return Classification("ask", description=f"{base} {method}")
        if t.startswith("-X") and len(t) > 2 and not t.startswith("-X="):
            method = t[2:].upper()
            if method not in SAFE_METHODS:
                return Classification("ask", description=f"{base} {method}")

        # Check -Q/--quote for FTP commands
        if t in {"-Q", "--quote"}:
            if i + 1 < len(tokens):
                ftp_cmd = tokens[i + 1].strip().strip("'\"").split()[0].upper()
                if ftp_cmd not in SAFE_FTP_COMMANDS:
                    return Classification("ask", description=f"{base} {t}")

    # Check for output file - return redirect_targets for config rule checking
    output_file = _extract_output_file(tokens)
    if output_file and output_file not in ("-", "/dev/null"):
        return Classification(
            "allow",
            description=base,
            redirect_targets=(output_file,),
        )

    return Classification("allow", description=base)
