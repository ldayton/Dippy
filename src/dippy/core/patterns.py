"""
Shared patterns and safe command sets for Dippy.
"""

import re


# === Simple Safe Commands ===
# These are always safe regardless of arguments (except output redirects)

SIMPLE_SAFE = frozenset({
    # File viewing
    "cat", "head", "tail", "less", "more", "bat", "tac",

    # Directory listing
    "ls", "ll", "la", "tree", "exa", "eza", "dir", "vdir", "lsof",

    # File info
    "stat", "file", "wc", "du", "df",

    # Path utilities
    "basename", "dirname", "pwd", "readlink", "realpath",

    # Search/filter (read-only)
    # Note: find has its own handler due to -exec/-delete flags
    "grep", "rg", "ripgrep", "ag", "ack", "fd", "locate",

    # Text processing (read-only)
    # Note: sed and sort have their own handlers due to -i/-o flags
    # Note: awk has its own handler due to -f and output redirects
    "uniq", "cut",
    "jq", "yq", "xq", "col", "comm", "diff", "expand", "fmt", "fold",
    "join", "nl", "paste", "tr", "tsort", "unexpand",

    # Checksums & hashing
    "md5sum", "sha1sum", "sha256sum", "sha512sum", "b2sum", "cksum",
    "md5", "shasum",

    # System info
    "whoami", "hostname", "uname", "date", "cal",
    "uptime", "free", "top", "htop", "ps", "pgrep", "id",
    "printenv", "echo", "printf",
    # Note: journalctl and dmesg have handlers due to modification flags

    # Network info (read-only)
    # Note: ip and ifconfig have handlers for modification commands
    "ping", "host", "dig", "nslookup", "traceroute", "netstat", "ss",
    "arp", "route",

    # Development tools (read-only)
    "which", "whereis", "type", "command", "hash",
    "man", "help", "info",

    # Testing and linting (safe operations)
    # Note: ruff has a handler due to "ruff clean"
    "pytest", "mypy", "black", "isort", "flake8",
    "pre-commit",
})


# === Unsafe Patterns ===
# These patterns indicate destructive operations
# Note: Output redirects (>, >>) are handled separately by has_output_redirect()
# which uses bashlex for proper parsing (handles quotes correctly)

UNSAFE_PATTERNS = [
    re.compile(r'\brm\s+\S'),      # rm anything
    re.compile(r'\bmv\s+'),        # mv (move/rename)
    re.compile(r'\bcp\s+'),        # cp (copy, but can overwrite)
    re.compile(r'\bchmod\s+'),     # chmod
    re.compile(r'\bchown\s+'),     # chown
    re.compile(r'\bsudo\s+'),      # sudo anything
    re.compile(r'\bdd\s+'),        # dd (disk destroyer)
]


# === Prefix Commands ===
# Commands that wrap other commands (we check what they wrap)

PREFIX_COMMANDS = frozenset({
    "time", "timeout", "nice", "nohup", "strace", "ltrace",
    "command", "builtin",
    # Note: xargs and env have their own handlers in cli/
})
