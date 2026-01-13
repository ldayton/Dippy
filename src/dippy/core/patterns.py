"""
Shared patterns and safe command sets for Dippy.
"""

import re


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
    }
)


# === Unsafe Patterns ===
# These patterns indicate destructive operations
# Note: Output redirects (>, >>) are handled separately by has_output_redirect()
# which uses bashlex for proper parsing (handles quotes correctly)

UNSAFE_PATTERNS = [
    re.compile(r"\brm\s+\S"),  # rm anything
    re.compile(r"\bmv\s+"),  # mv (move/rename)
    re.compile(r"\bcp\s+"),  # cp (copy, but can overwrite)
    re.compile(r"\bchmod\s+"),  # chmod
    re.compile(r"\bchown\s+"),  # chown
    re.compile(r"\bsudo\s+"),  # sudo anything
    re.compile(r"\bdd\s+"),  # dd (disk destroyer)
]


# === Prefix Commands ===
# Commands that wrap other commands (we check what they wrap)

PREFIX_COMMANDS = frozenset(
    {
        "time",
        "timeout",
        "nice",
        "nohup",
        "strace",
        "ltrace",
        "command",
        "builtin",
        # Note: xargs and env have their own handlers in cli/
    }
)
