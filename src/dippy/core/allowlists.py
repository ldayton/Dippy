"""
Allowlists for Dippy - known safe commands and transparent wrappers.
"""

# === Simple Safe Commands ===
# These are always safe regardless of arguments (except output redirects)

SIMPLE_SAFE = frozenset(
    {
        # === File Content Viewing ===
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "bat",
        "tac",
        "od",
        # === Directory Listing ===
        "ls",
        "ll",
        "la",
        "tree",
        "exa",
        "eza",
        "dir",
        "vdir",
        # === File & Disk Information ===
        "stat",
        "file",
        "wc",
        "du",
        "df",
        # === Path Utilities ===
        "basename",
        "dirname",
        "pwd",
        "cd",
        "readlink",
        "realpath",
        # === Search & Find ===
        "grep",
        "rg",
        "ripgrep",
        "ag",
        "ack",
        "locate",
        # === Text Processing ===
        "uniq",
        "cut",
        "col",
        "comm",
        "diff",
        "expand",
        "fmt",
        "fold",
        "join",
        "nl",
        "paste",
        "tr",
        "tsort",
        "unexpand",
        # === Structured Data (JSON/YAML/XML) ===
        "jq",
        "yq",
        "xq",
        # === Encoding & Decoding ===
        "base64",
        # === Checksums & Hashing ===
        "md5sum",
        "sha1sum",
        "sha256sum",
        "sha512sum",
        "b2sum",
        "cksum",
        "md5",
        "shasum",
        # === User & System Identity ===
        "whoami",
        "hostname",
        "uname",
        "id",
        # === Date & Time ===
        "date",
        "cal",
        "uptime",
        # === Process & Resource Monitoring ===
        "ps",
        "pgrep",
        "top",
        "htop",
        "free",
        "lsof",
        # === Environment & Output ===
        "printenv",
        "echo",
        "printf",
        # === Network Diagnostics ===
        "ping",
        "host",
        "dig",
        "nslookup",
        "traceroute",
        "netstat",
        "ss",
        "arp",
        "route",
        # === Command Lookup & Help ===
        "which",
        "whereis",
        "type",
        "command",
        "hash",
        "man",
        "help",
        "info",
        # === Code Quality & Linting ===
        "mypy",
        "black",
        "isort",
        "flake8",
        "pre-commit",
        # === Shell Builtins & Utilities ===
        "true",
        "false",
        "sleep",
        "read",  # shell builtin, reads from stdin
    }
)


# === Transparent Wrappers ===
# Commands that wrap other commands - we analyze the inner command instead

WRAPPER_COMMANDS = frozenset(
    {
        "time",
        "timeout",
        "nice",
        "nohup",
        "strace",
        "ltrace",
        "command",
        "builtin",
    }
)
