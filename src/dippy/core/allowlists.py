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
        "hexdump",
        "ldd",
        "nm",
        "objdump",
        "otool",
        "readelf",
        "size",
        "strings",
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
        "colrm",
        "column",
        "comm",
        "cmp",
        "diff",
        "expand",
        "bc",
        "dc",
        "expr",
        "fmt",
        "fold",
        "join",
        "nl",
        "paste",
        "rev",
        "seq",
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
        "sum",
        # === User & System Identity ===
        "whoami",
        "hostname",
        "uname",
        "sw_vers",
        "id",
        "groups",
        "last",
        "locale",
        "w",
        "who",
        # === Date & Time ===
        "date",
        "cal",
        "uptime",
        # === Process & Resource Monitoring ===
        "dmesg",
        "iostat",
        "ps",
        "pgrep",
        "top",
        "htop",
        "free",
        "fuser",
        "lsof",
        "nettop",
        "ioreg",
        "powermetrics",
        "system_profiler",
        "vm_stat",
        "vmstat",
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
        "mtr",
        "netstat",
        "ss",
        "arp",
        "route",
        "whois",
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
        # === Terminal ===
        "clear",
        "reset",
        "tput",
        "tty",
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
